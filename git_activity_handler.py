#!/usr/bin/env python3
import os
import random
import subprocess
import time
import sys
import logging
from datetime import datetime, timedelta
import argparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.expanduser("~/git_handler_log.txt")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("git_handler")

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Ensure required files exist
def ensure_files_exist():
    if not os.path.exists("number.txt"):
        with open("number.txt", "w") as f:
            f.write("0")
    if not os.path.exists(".last_run"):
        save_last_run_time()

def read_number():
    with open("number.txt", "r") as f:
        return int(f.read().strip())

def write_number(num):
    with open("number.txt", "w") as f:
        f.write(str(num))

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
        with open(".last_run", "r") as f:
            return datetime.fromisoformat(f.read().strip())
    except FileNotFoundError:
        return datetime.min
    except ValueError:
        logger.error("Invalid date format in .last_run file")
        return datetime.min

def save_last_run_time():
    with open(".last_run", "w") as f:
        f.write(datetime.now().isoformat())

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
    with open("timestamp.txt", "w") as f:
        f.write(f"Last updated: {timestamp}")
    return timestamp

def git_commit():
    # Stage the changes
    create_timestamp_file()  # Add this line to create the timestamp file
    subprocess.run(["git", "add", "number.txt", "timestamp.txt"])
    # Create commit with current date
    if "FANCY_JOB_USE_LLM" in os.environ:
        commit_message = generate_random_commit_message()
    else:
        date = datetime.now().strftime("%Y-%m-%d")
        commit_message = f"Update number: {date}"
    subprocess.run(["git", "commit", "-m", commit_message])

def git_push():
    # Push the committed changes to GitHub
    result = subprocess.run(["git", "push"], capture_output=True, text=True)
    if result.returncode == 0:
        print("Changes pushed to GitHub successfully.")
    else:
        print("Error pushing to GitHub:")
        print(result.stderr)

def schedule_next_run():
    """Schedule the next run using systemd timer"""
    # Generate random time for tomorrow
    random_hour = random.randint(9, 23)  # Between 9 AM and 11 PM
    random_minute = random.randint(0, 59)
    
    # Calculate time until next run in seconds
    now = datetime.now()
    tomorrow = now.date() + timedelta(days=1)
    next_run_time = datetime(
        tomorrow.year, tomorrow.month, tomorrow.day, 
        random_hour, random_minute
    )
    
    seconds_until_next_run = (next_run_time - now).total_seconds()
    
    logger.info(f"Next run scheduled for {next_run_time} ({random_hour}:{random_minute:02d})")
    
    # Create systemd timer command
    command = [
        "systemd-run", 
        "--user", 
        f"--on-calendar={tomorrow.year}-{tomorrow.month:02d}-{tomorrow.day:02d} {random_hour}:{random_minute:02d}:00",
        f"{sys.executable} {os.path.abspath(__file__)} --run-once"
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Next run scheduled successfully")
        else:
            logger.error(f"Failed to schedule next run: {result.stderr}")
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
    parser = argparse.ArgumentParser(description="Git Activity Handler")
    parser.add_argument("--run-once", action="store_true", help="Run once and exit")
    parser.add_argument("--install", action="store_true", help="Install as systemd service")
    args = parser.parse_args()

    ensure_files_exist()
    
    if args.install:
        install_service()
        return
    
    if args.run_once:
        perform_daily_update()
        # Schedule next run
        schedule_next_run()
        return
    
    # Default mode - run and schedule next run
    logger.info("Starting git activity handler...")
    perform_daily_update()
    schedule_next_run()

def install_service():
    """Install as systemd service"""
    # Create systemd service file
    service_content = f"""[Unit]
Description=Git Activity Handler Service
After=network.target

[Service]
ExecStart={sys.executable} {os.path.abspath(__file__)} --run-once
WorkingDirectory={script_dir}
Type=oneshot
Restart=no
User={os.environ.get('USER', os.environ.get('USERNAME', 'user'))}

[Install]
WantedBy=multi-user.target
"""

    # Create timer file to run at startup
    timer_content = """[Unit]
Description=Git Activity Handler Timer

[Timer]
OnBootSec=60
OnUnitActiveSec=86400
RandomizedDelaySec=3600
Persistent=true

[Install]
WantedBy=timers.target
"""

    # Write service files
    service_path = os.path.expanduser("~/.config/systemd/user/git-activity-handler.service")
    timer_path = os.path.expanduser("~/.config/systemd/user/git-activity-handler.timer")
    
    os.makedirs(os.path.dirname(service_path), exist_ok=True)
    
    with open(service_path, "w") as f:
        f.write(service_content)
    
    with open(timer_path, "w") as f:
        f.write(timer_content)
    
    # Enable and start the service
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"])
        subprocess.run(["systemctl", "--user", "enable", "git-activity-handler.timer"])
        subprocess.run(["systemctl", "--user", "start", "git-activity-handler.timer"])
        
        print("\nService installed successfully!")
        print("The git-activity-handler service will run at system startup")
        print("and ensure daily commits are made.\n")
        print("To check service status: systemctl --user status git-activity-handler")
        print("To check timer status: systemctl --user status git-activity-handler.timer")
    except Exception as e:
        print(f"Error installing service: {str(e)}")

if __name__ == "__main__":
    main()
