#!/usr/bin/env python3
import os
import random
import subprocess
import time
from datetime import datetime

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)


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

def save_last_run_time():
    with open(".last_run", "w") as f:
        f.write(datetime.now().isoformat())

def should_run_today():
    last_run = get_last_run_time()
    now = datetime.now()
    return (now.date() - last_run.date()).days >= 1

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


def update_cron_with_random_time():
    # Generate random hour (0-23) and minute (0-59)
    random_hour = random.randint(0, 23)
    random_minute = random.randint(0, 59)

    # Define the new cron job command
    new_cron_command = f"{random_minute} {random_hour} * * * cd {script_dir} && python3 {os.path.join(script_dir, 'update_number.py')}\n"

    # Get the current crontab
    cron_file = "/tmp/current_cron"
    os.system(
        f"crontab -l > {cron_file} 2>/dev/null || true"
    )  # Save current crontab, or create a new one if empty

    # Update the crontab file
    with open(cron_file, "r") as file:
        lines = file.readlines()

    with open(cron_file, "w") as file:
        for line in lines:
            # Remove existing entry for `update_number.py` if it exists
            if "update_number.py" not in line:
                file.write(line)
        # Add the new cron job at the random time
        file.write(new_cron_command)

    # Load the updated crontab
    os.system(f"crontab {cron_file}")
    os.remove(cron_file)

    print(f"Cron job updated to run at {random_hour}:{random_minute} tomorrow.")


def main():
    print("Starting continuous monitoring...")
    while True:
        try:
            if should_run_today():
                print(f"Running daily update at {datetime.now()}")
                current_number = read_number()
                new_number = current_number + 1
                write_number(new_number)
                git_commit()
                git_push()
                save_last_run_time()
                print("Successfully updated and pushed changes")
            
            # Check every hour
            time.sleep(3600)
        except Exception as e:
            print(f"Error: {str(e)}")
            time.sleep(300)  # Wait 5 minutes on error


if __name__ == "__main__":
    main()
