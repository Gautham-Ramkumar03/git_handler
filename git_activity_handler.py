#!/usr/bin/env python3
import os
import random
import subprocess
import time
import sys
import logging
from datetime import datetime, timedelta
import argparse
import traceback

# Set up logging
log_file = os.path.expanduser("~/git_handler_log.txt")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("git_handler")

# Always log uncaught exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

# Get absolute path to script directory
script_dir = os.path.dirname(os.path.abspath(__file__))

def ensure_files_exist():
    # Use absolute paths
    number_path = os.path.join(script_dir, "number.txt")
    last_run_path = os.path.join(script_dir, ".last_run")
    
    if not os.path.exists(number_path):
        with open(number_path, "w") as f:
            f.write("0")
        logger.info(f"Created number.txt file at {number_path}")
    
    if not os.path.exists(last_run_path):
        with open(last_run_path, "w") as f:
            f.write(datetime.now().isoformat())
        logger.info(f"Created .last_run file at {last_run_path}")

def read_number():
    try:
        with open(os.path.join(script_dir, "number.txt"), "r") as f:
            return int(f.read().strip())
    except Exception as e:
        logger.error(f"Error reading number: {str(e)}")
        return 0

def write_number(num):
    try:
        with open(os.path.join(script_dir, "number.txt"), "w") as f:
            f.write(str(num))
    except Exception as e:
        logger.error(f"Error writing number: {str(e)}")

def generate_random_commit_message():
    from transformers import pipeline

    generator = pipeline(
        "text-generation",
        model="openai-community/gpt2",
    )
    prompt = """
        Generate a Git commit message following the Conventional Commits standard. The message should include a type, an optional scope, and a subject.Please keep it short. Here are some examples:

        - feat(auth): add user authentication module
        - fix(api): resolve null pointer exception in user endpoint
        - docs(readme): update installation instructions
        - chore(deps): upgrade lodash to version 4.17.21
        - refactor(utils): simplify date formatting logic

        Now, generate a new commit message:
    """
    generated = generator(
        prompt,
        max_new_tokens=50,
        num_return_sequences=1,
        temperature=0.9,  # Slightly higher for creativity
        top_k=50,  # Limits sampling to top 50 logits
        top_p=0.9,  # Nucleus sampling for diversity
        truncation=True,
    )
    text = generated[0]["generated_text"]

    if "- " in text:
        return text.rsplit("- ", 1)[-1].strip()
    else:
        raise ValueError(f"Unexpected generated text {text}")

def get_last_run_time():
    try:
        with open(os.path.join(script_dir, ".last_run"), "r") as f:
            return datetime.fromisoformat(f.read().strip())
    except FileNotFoundError:
        logger.warning("No last run file found, creating one")
        save_last_run_time()
        return datetime.min
    except ValueError as e:
        logger.error(f"Invalid date format in .last_run file: {str(e)}")
        return datetime.min
    except Exception as e:
        logger.error(f"Unexpected error reading last run time: {str(e)}")
        return datetime.min

def save_last_run_time():
    try:
        with open(os.path.join(script_dir, ".last_run"), "w") as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        logger.error(f"Error saving last run time: {str(e)}")

def should_run_today():
    last_run = get_last_run_time()
    now = datetime.now()
    return (now.date() - last_run.date()).days >= 1

def days_since_last_run():
    last_run = get_last_run_time()
    now = datetime.now()
    return (now.date() - last_run.date()).days

def create_timestamp_file():
    """Create a timestamp file to ensure we have unique content each day"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(os.path.join(script_dir, "timestamp.txt"), "w") as f:
            f.write(f"Last updated: {timestamp}")
        return timestamp
    except Exception as e:
        logger.error(f"Error creating timestamp file: {str(e)}")
        return timestamp

def git_commit():
    try:
        # Move to the script directory first
        os.chdir(script_dir)
        
        # Stage the changes
        create_timestamp_file()
        subprocess.run(["git", "add", "number.txt", "timestamp.txt"], check=True)
        
        # Create commit with current date
        if "FANCY_JOB_USE_LLM" in os.environ:
            try:
                commit_message = generate_random_commit_message()
            except Exception as e:
                logger.error(f"Error generating message with LLM: {str(e)}")
                date = datetime.now().strftime("%Y-%m-%d")
                commit_message = f"Update number: {date}"
        else:
            date = datetime.now().strftime("%Y-%m-%d")
            commit_message = f"Update number: {date}"
            
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        logger.info(f"Created commit: {commit_message}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error in git_commit: {str(e)}")

def git_push():
    try:
        # Move to the script directory first
        os.chdir(script_dir)
        
        # Push the committed changes to GitHub
        result = subprocess.run(["git", "push"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Changes pushed to GitHub successfully.")
        else:
            logger.error(f"Error pushing to GitHub: {result.stderr}")
    except Exception as e:
        logger.error(f"Error in git_push: {str(e)}")

def schedule_next_run():
    """Schedule the next run using systemd timer or fallback mechanism"""
    try:
        # Generate random time for tomorrow
        random_hour = random.randint(9, 23)  # Between 9 AM and 11 PM
        random_minute = random.randint(0, 59)
        
        # Calculate time until next run
        now = datetime.now()
        tomorrow = now.date() + timedelta(days=1)
        next_run_time = datetime(
            tomorrow.year, tomorrow.month, tomorrow.day, 
            random_hour, random_minute
        )
        
        logger.info(f"Next run scheduled for {next_run_time} ({random_hour}:{random_minute:02d})")
        
        # Try to use systemd-run first
        try:
            command = [
                "systemd-run", 
                "--user", 
                f"--on-calendar={tomorrow.year}-{tomorrow.month:02d}-{tomorrow.day:02d} {random_hour}:{random_minute:02d}:00",
                f"{sys.executable} {os.path.abspath(__file__)} --run-once"
            ]
            
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("Next run scheduled successfully with systemd-run")
                return
            else:
                logger.warning(f"Failed to schedule with systemd-run: {result.stderr}")
        except Exception as e:
            logger.warning(f"Error using systemd-run: {str(e)}")
        
        # Fallback to using at command if available
        try:
            at_time = f"{random_hour:02d}:{random_minute:02d}"
            at_date = tomorrow.strftime("%Y-%m-%d")
            at_cmd = f"cd {script_dir} && {sys.executable} {os.path.abspath(__file__)} --run-once"
            
            # Create temp script for at
            temp_script = os.path.join(script_dir, ".run_script.sh")
            with open(temp_script, "w") as f:
                f.write("#!/bin/sh\n")
                f.write(f"cd {script_dir}\n")
                f.write(f"{sys.executable} {os.path.abspath(__file__)} --run-once\n")
            
            os.chmod(temp_script, 0o755)
            
            # Schedule with at
            at_process = subprocess.Popen(
                ["at", at_time, at_date], 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            at_process.communicate(input=f"{temp_script}\n")
            
            if at_process.returncode == 0:
                logger.info(f"Next run scheduled with 'at' command for {at_date} {at_time}")
                return
            else:
                logger.warning("Failed to schedule with 'at' command")
        except Exception as e:
            logger.warning(f"Error using 'at' command: {str(e)}")
        
        # Final fallback - create a simple launcher script
        logger.info("Creating fallback launcher script")
        launcher_path = os.path.expanduser("~/run_git_handler.sh")
        with open(launcher_path, "w") as f:
            f.write("#!/bin/bash\n")
            f.write(f"cd {script_dir}\n")
            f.write(f"{sys.executable} {os.path.abspath(__file__)} --run-once\n")
        
        os.chmod(launcher_path, 0o755)
        logger.info(f"Created launcher script at {launcher_path}")
        logger.info("Please add this script to your startup applications or run it manually")
        
    except Exception as e:
        logger.error(f"Error scheduling next run: {str(e)}")

def process_missed_days():
    """Process missed days if the laptop was off"""
    days_missed = days_since_last_run()
    
    if days_missed <= 0:
        return False
        
    logger.info(f"Detected {days_missed} missed day(s). Processing updates...")
    
    # Update number for each missed day
    current_number = read_number()
    new_number = current_number + days_missed
    write_number(new_number)
    
    # Commit with message mentioning missed days
    create_timestamp_file()
    subprocess.run(["git", "add", "number.txt", "timestamp.txt"])
    
    if "FANCY_JOB_USE_LLM" in os.environ:
        commit_message = generate_random_commit_message()
    else:
        commit_message = f"Update for {days_missed} missed day(s): {datetime.now().strftime('%Y-%m-%d')}"
    
    subprocess.run(["git", "commit", "-m", commit_message])
    git_push()
    save_last_run_time()
    
    logger.info(f"Successfully updated for missed days. New number: {new_number}")
    return True

def perform_daily_update():
    """Perform a single daily update"""
    try:
        # First check if we missed any days
        if process_missed_days():
            return True
            
        # If we didn't miss days but need to run today
        if should_run_today():
            logger.info(f"Running daily update at {datetime.now()}")
            current_number = read_number()
            new_number = current_number + 1
            write_number(new_number)
            git_commit()
            git_push()
            save_last_run_time()
            logger.info("Successfully updated and pushed changes")
            return True
        else:
            logger.info("No update needed today")
            return False
    except Exception as e:
        logger.error(f"Error during daily update: {str(e)}")
        return False

def main():
    try:
        # Log system information for debugging
        logger.info(f"Starting git-activity-handler with Python {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Script directory: {script_dir}")
        
        parser = argparse.ArgumentParser(description="Git Activity Handler")
        parser.add_argument("--run-once", action="store_true", help="Run once and exit")
        parser.add_argument("--install", action="store_true", help="Install as systemd service")
        args = parser.parse_args()
        
        # Force change to script directory
        os.chdir(script_dir)
        ensure_files_exist()
        
        if args.install:
            install_service()
            return
        
        if args.run_once:
            logger.info("Running in single execution mode")
            performed_update = perform_daily_update()
            # Schedule next run only if this run was successful
            if performed_update:
                schedule_next_run()
            return
        
        # Default mode - run and schedule next run
        logger.info("Starting git activity handler in default mode...")
        performed_update = perform_daily_update()
        if performed_update:
            schedule_next_run()
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
        logger.error(traceback.format_exc())
        return 1
    return 0

def install_service():
    """Install as systemd service"""
    logger.info("Installing git-activity-handler service...")
    
    # Create systemd service file - with improved settings
    service_content = f"""[Unit]
Description=Git Activity Handler Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={sys.executable} {os.path.abspath(__file__)} --run-once
WorkingDirectory={script_dir}
Environment="PATH={os.environ.get('PATH', '/usr/bin:/bin')}"
Environment="HOME={os.environ.get('HOME', '/home/user')}"
StandardOutput=append:{log_file}
StandardError=append:{log_file}

[Install]
WantedBy=default.target
"""

    # Create timer file to run at startup and daily
    timer_content = """[Unit]
Description=Git Activity Handler Timer

[Timer]
OnBootSec=2min
OnUnitActiveSec=12h
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
"""

    # Write service files
    service_path = os.path.expanduser("~/.config/systemd/user/git-activity-handler.service")
    timer_path = os.path.expanduser("~/.config/systemd/user/git-activity-handler.timer")
    
    os.makedirs(os.path.dirname(service_path), exist_ok=True)
    
    try:
        with open(service_path, "w") as f:
            f.write(service_content)
        
        with open(timer_path, "w") as f:
            f.write(timer_content)
        
        logger.info(f"Service files created at {service_path} and {timer_path}")
        
        # Generate desktop entry for autostart
        autostart_dir = os.path.expanduser("~/.config/autostart")
        autostart_path = os.path.join(autostart_dir, "git-activity-handler.desktop")
        os.makedirs(autostart_dir, exist_ok=True)
        
        desktop_content = f"""[Desktop Entry]
Type=Application
Name=Git Activity Handler
Exec={sys.executable} {os.path.abspath(__file__)} --run-once
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
"""
        
        with open(autostart_path, "w") as f:
            f.write(desktop_content)
        
        logger.info(f"Created autostart entry at {autostart_path}")
        
        # Enable and start the service
        try:
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "--user", "enable", "git-activity-handler.timer"], check=True)
            subprocess.run(["systemctl", "--user", "start", "git-activity-handler.timer"], check=True)
            
            # Test the service directly
            try:
                subprocess.run(["systemctl", "--user", "start", "git-activity-handler.service"], check=True)
                logger.info("Service started successfully for testing")
            except Exception as e:
                logger.warning(f"Test service start failed: {str(e)}")
            
            logger.info("\nService installed successfully!")
            logger.info("The git-activity-handler service will run at system startup")
            logger.info("and ensure daily commits are made.\n")
            print("\nService installed successfully!")
            print("The git activity handler will run at system startup")
            print(f"Logs will be written to: {log_file}")
            print("\nTo check service status: systemctl --user status git-activity-handler")
            print("To check timer status: systemctl --user status git-activity-handler.timer")
            print(f"To run manually: {sys.executable} {os.path.abspath(__file__)} --run-once")
        except Exception as e:
            logger.error(f"Error enabling/starting service: {str(e)}")
            # Create backup launcher script
            create_launcher_script()
    except Exception as e:
        logger.error(f"Error creating service files: {str(e)}")
        # Create backup launcher script
        create_launcher_script()

def create_launcher_script():
    """Create a simple launcher script as fallback"""
    launcher_path = os.path.expanduser("~/run_git_handler.sh")
    try:
        with open(launcher_path, "w") as f:
            f.write("#!/bin/bash\n")
            f.write(f"cd {script_dir}\n")
            f.write(f"{sys.executable} {os.path.abspath(__file__)} --run-once\n")
        
        os.chmod(launcher_path, 0o755)
        print(f"\nCreated fallback launcher script at: {launcher_path}")
        print("Add this script to your startup applications or run it manually")
    except Exception as e:
        logger.error(f"Error creating launcher script: {str(e)}")

if __name__ == "__main__":
    sys.exit(main())
