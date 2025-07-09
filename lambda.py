import os
import subprocess
import time
import re
import uuid # For generating unique names
from dotenv import load_dotenv
import google.generativeai as genai

# --- Configuration ---
# Replace with your GitHub repository URL
GITHUB_REPO_URL = "https://github.com/pankajpachahara/automated_lambda1.git"
AWS_REGION = "ap-south-1" # Mumbai region
PROJECT_NAME = "pankaj-devops-lambda" # Base name for resources
LAMBDA_RUNTIME = "nodejs18.x" # Or nodejs20.x

# Unique identifiers for S3 bucket and DynamoDB table to avoid conflicts
UNIQUE_ID = str(uuid.uuid4())[:8] # Short unique ID
S3_STATE_BUCKET_NAME = f"{PROJECT_NAME}-tfstate-{UNIQUE_ID}"
DDB_LOCK_TABLE_NAME = f"{PROJECT_NAME}-tf-lock-{UNIQUE_ID}"

# --- Helper Functions ---

import re # Make sure 're' is imported at the top of your script

def extract_code_block(response_text, filename_hint, lang_tag):
    """
    Extracts a code block from the Gemini response based on filename hint and language tag.
    Assumes the format: ### filename language\n```[lang]\nCODE\n```
    Made more robust for leading/trailing whitespace around fences and headers.
    """
    # pattern = re.compile( # This was your previous pattern
    #     rf"### {re.escape(filename_hint)} {re.escape(lang_tag)}\s*\n```(?:{re.escape(lang_tag)})?\s*\n(.*?)\n```",
    #     re.DOTALL | re.IGNORECASE
    # )

    # *** THIS IS THE CORRECTED REGEX ***
    pattern = re.compile(
        # Matches optional leading whitespace on the line, then '###', filename, and lang tag
        rf"^\s*### {re.escape(filename_hint)} {re.escape(lang_tag)}\s*\n"
        # Matches optional leading whitespace before the opening code fence, then the fence itself
        rf"\s*```(?:{re.escape(lang_tag)})?\s*\n"
        # Captures the actual code content (non-greedy, matches anything including newlines)
        r"(.*?)\n"
        # Matches optional leading whitespace before the closing code fence, then the fence itself
        r"^\s*```",
        re.DOTALL | re.IGNORECASE | re.MULTILINE # MULTILINE makes '^' and '$' match start/end of lines
    )
    # *** END CORRECTED REGEX ***

    match = pattern.search(response_text)
    if match:
        return match.group(1).strip()
    return None

# ... (rest of your lambda.py script)

import os # Make sure os is imported at the top of your script

def write_file(path, content):
    """Helper to write content to a file, creating directories if needed."""
    try:
        # Check if the path has a directory component.
        # If it's just a filename (like "main.tf"), dirname will be empty.
        dir_name = os.path.dirname(path)
        if dir_name: # Only create directory if dir_name is not empty (i.e., if it's not the current directory)
            os.makedirs(dir_name, exist_ok=True)
        
        with open(path, "w") as f:
            f.write(content)
        print(f"Created {path}")
    except IOError as e:
        print(f"Error writing file {path}: {e}")
        exit(1)

def call_gemini_and_save(prompt_text, output_filename, lang_tag, preamble_text=None):
    """
    Calls Gemini API with a prompt, extracts a specific code block, and saves it.
    Args:
        prompt_text (str): The main prompt to send to Gemini.
        output_filename (str): The full path to the file (e.g., "backend-bootstrap/backend.tf").
        lang_tag (str): The expected language tag (e.g., "hcl", "yaml").
        preamble_text (str, optional): Text to prepend to the prompt (e.g., existing file content).
    Returns:
        str: The content of the extracted code block, or None if not found.
    """
    full_prompt = prompt_text
    if preamble_text:
        full_prompt = f"{preamble_text}\n\n---\n\n{prompt_text}"

    print(f"\n--- Sending prompt for {output_filename} ---")
    try:
        response = model.generate_content(full_prompt)
        reply = response.text
        # print(f"Gemini Raw Response for {output_filename}:\n{reply}\n--- End Raw Response ---") # For debugging

        code_content = extract_code_block(reply, output_filename, lang_tag)

        if code_content:
            write_file(output_filename, code_content)
            return code_content
        else:
            print(f"Warning: No {lang_tag} code block found for {output_filename} in Gemini's response.")
            print("AI Response was:\n", reply)
            return None

    except Exception as e:
        print(f"Error while getting Gemini response for {output_filename}: {e}")
        return None

def run_terraform_command(command, cwd=None):
    """Helper to run terraform commands."""
    print(f"\n--- Running: {' '.join(command)} in {cwd if cwd else os.getcwd()} ---")
    try:
        result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Stderr:\n", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error during Terraform command: {' '.join(command)}")
        print("Stdout:\n", e.stdout)
        print("Stderr:\n", e.stderr)
        return False
    except FileNotFoundError:
        print("Terraform command not found. Please ensure Terraform is installed and in your PATH.")
        return False

# --- Main Script Execution ---

def main():
    # Step 1: Load .env
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("GEMINI_API_KEY not found. Please check your .env file and ensure it contains GEMINI_API_KEY=YOUR_KEY.")
        exit(1)

    # Step 2: Configure Gemini
    global model
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro')

    # Step 3: Create all necessary directories upfront
    print("Creating project directories...")
    os.makedirs(".github/workflows", exist_ok=True)
    os.makedirs("backend-bootstrap", exist_ok=True)
    os.makedirs("src", exist_ok=True)
    print("Directories created.")

    # --- File Generation Prompts ---

    # Prompt 1: Terraform Backend
    prompt_backend = f"""
    You are an expert DevOps engineer.
    Generate only the necessary Terraform configuration for the `backend-bootstrap/backend.tf` file.
This file should define **ONLY** the AWS resources (`aws_s3_bucket`, `aws_dynamodb_table`, and `aws_s3_bucket_public_access_block`) needed to create an S3 bucket and DynamoDB table to store the Terraform state and lock it.
**IMPORTANT: DO NOT include a `terraform {{ backend ... }}` block or any `provider` block in this file.** This file's sole purpose is to define resources to be created, not to configure Terraform's own state backend or AWS provider.
Ensure S3 bucket versioning and server-side encryption (AES256) are enabled.
**For public access blocking, create a separate `aws_s3_bucket_public_access_block` resource and explicitly link it to the S3 state bucket.** Make sure to block all public access settings (block_public_acls, block_public_policy, ignore_public_acls, restrict_public_buckets). DO NOT configure public access blocking directly within the `aws_s3_bucket` resource itself.
The DynamoDB table should be named `{DDB_LOCK_TABLE_NAME}` and have `LockID` as the primary key with PAY_PER_REQUEST billing mode.
The S3 bucket should be named `{S3_STATE_BUCKET_NAME}`.
The S3 bucket should also have `force_destroy = true` for easy cleanup in development.
Output must be in this exact format:
### backend-bootstrap/backend.tf hcl
    ```hcl
    # Terraform code goes here
    ```
    """

    # Prompt 2: Initial Core Infrastructure (VPC, Subnets, Security Groups, IAM)
    prompt_core_infra = f"""
    You are an expert DevOps engineer.
    Generate the initial Terraform configuration for `main.tf` and `variables.tf` files.
    These files should define:
    - A new AWS VPC with CIDR block "10.0.0.0/16".
    - Two public subnets in different availability zones.
    - An Internet Gateway and route table associations.
    - A security group for the Lambda function (allowing inbound from ALB).
    - A security group for the ALB (allowing HTTP inbound from anywhere).
    - IAM role and policy for the Lambda function with basic execution permissions (CloudWatch logs, ENI management for VPC).
    - An S3 bucket for storing the Lambda deployment package (e.g., `{PROJECT_NAME}-lambda-code-${{data.aws_caller_identity.current.account_id}}`).
    - The `main.tf` should also contain the Terraform backend configuration, referencing the S3 bucket `{S3_STATE_BUCKET_NAME}` and DynamoDB table `{DDB_LOCK_TABLE_NAME}` created in the previous step.
    - Variables for `aws_region` (default: `{AWS_REGION}`), `project_name` (default: `{PROJECT_NAME}`), and `environment` (default: `development`).
    - Ensure no Lambda or ALB resources are defined yet, only the networking, security, and IAM components.
    - Include a data source for `aws_caller_identity` to get the account ID.

    Output must be in this exact format, providing both files:
    ### main.tf hcl
    ```hcl
    # main.tf code goes here
    ```

    ### variables.tf hcl
    ```hcl
    # variables.tf code goes here
    ```
    """

    # Define the literal string for S3 bucket interpolation for Gemini
    # This ensures Python does not try to interpret `aws_s3_bucket.lambda_code_bucket.id`
    S3_CODE_BUCKET_INTERPOLATION_STRING = "${aws_s3_bucket.lambda_code_bucket.id}"

    # Prompt 3: Update main.tf with Lambda and ALB
    prompt_update_main_tf = f"""
    You are an expert DevOps engineer.
    Here is the current content of my `main.tf` file:
    ```hcl
    {{current_main_tf_content}}
    ```

    Please update this `main.tf` file to include the AWS Lambda function and the Application Load Balancer (ALB).
    - For the Lambda function:
        - Name: `{PROJECT_NAME}-nodejs-app`
        - Handler: `index.handler`
        - Runtime: `{LAMBDA_RUNTIME}`
        - Timeout: 30 seconds, Memory: 128 MB
        - It should run in the VPC, use the IAM role defined previously, and be associated with the Lambda security group.
        - The code will be uploaded to the S3 bucket `{S3_CODE_BUCKET_INTERPOLATION_STRING}` with key `lambda.zip`.
        - Include a `source_code_hash` (even if placeholder, as GitHub Actions will update it).
    - For the ALB:
        - Name: `{PROJECT_NAME}-alb`
        - Type: application load balancer, internet-facing.
        - Security group should be the one defined previously.
        - Subnets: the public subnets defined previously.
        - Create a target group (`lambda_tg`) of type `lambda` that targets the Lambda function.
        - Create an HTTP listener on port 80 that forwards traffic to this target group.
    - Grant the ALB permission to invoke the Lambda function using `aws_lambda_permission`.
    - Add an `alb_dns_name` output.

    Output the complete, updated `main.tf` file content in the following format:
    ### main.tf hcl
    ```hcl
    # Updated main.tf code goes here
    ```
    """

    # Prompt 4: GitHub Actions Workflow
    # Note: The AWS_ACCOUNT_ID secret needs to be set in GitHub repository settings.
    prompt_github_actions = f"""
    You are an expert DevOps engineer.
    Generate the GitHub Actions workflow file for `.github/workflows/deploy.yml`.
    This workflow should:
    - Trigger on `push` to the `main` branch.
    - Use `ubuntu-latest` as the runner.
    - Define necessary permissions for OIDC to assume an AWS role (id-token: write, contents: read).
    - Set up Node.js (v18.x).
    - Install Node.js dependencies (e.g., `npm install` in `src/`).
    - Package the Node.js application from `src/` into a `lambda.zip` file. The `src` directory contains `index.js`. Use `zip -r lambda.zip .` from inside the `src` directory.
    - Set up Terraform using `hashicorp/setup-terraform@v2`.
    - Configure AWS credentials using OIDC for an IAM role named `arn:aws:iam::${{{{ secrets.AWS_ACCOUNT_ID }}}}:role/GitHubActionsRoleForDeployment`.
    - Run `terraform init` (ensuring it uses the S3 backend and DynamoDB lock table, region `{AWS_REGION}`).
    - Run `terraform plan`.
    - Run `terraform apply -auto-approve`.
    - The `lambda.zip` file should be uploaded to the S3 bucket created by Terraform (you can use `aws s3 cp` or ensure Terraform's `aws_lambda_function` resource uploads it from the local path). Ensure the Lambda `source_code_hash` is updated dynamically during packaging.

    Output must be in this exact format:
    ### .github/workflows/deploy.yml yaml
    ```yaml
    # GitHub Actions workflow code goes here
    ```
    """

    # --- Execution Steps ---

    # Step 4.1: Generate backend-bootstrap/backend.tf
    backend_tf_content = call_gemini_and_save(prompt_backend, "backend-bootstrap/backend.tf", "hcl")
    if not backend_tf_content:
        print("Failed to generate backend-bootstrap/backend.tf. Exiting.")
        exit(1)

    # Step 4.2: Run Terraform init + apply for backend only
    # ... (rest of the script remains the same up to this point)

    # Step 4.2: Run Terraform init + apply for backend only
    print("\n--- Running Terraform backend init/apply ---")
    current_dir = os.getcwd()

    # --- THIS IS THE CRITICAL CHANGE ---
    # When initializing the backend-bootstrap, it should NOT try to use a remote backend.
    # It should use local state to CREATE the S3/DDB resources.
    if not run_terraform_command(["terraform", "init"], cwd="backend-bootstrap"):
        print("Terraform backend init failed. Exiting.")
        exit(1)
    # --- END CRITICAL CHANGE ---

    # This terraform apply will now create the S3 bucket and DynamoDB table
    # using its local state.
    if not run_terraform_command(["terraform", "apply", "-auto-approve"], cwd="backend-bootstrap"):
        print("Terraform backend apply failed. Exiting.")
        exit(1)
    print("Terraform backend setup complete. S3 bucket and DynamoDB table for state have been created.")

# ... (rest of the script continues from here)

    # Step 4.3: Generate initial main.tf and variables.tf
    print("\n--- Sending prompt for main.tf and variables.tf (initial infrastructure) ---")
    try:
        response_core_infra = model.generate_content(prompt_core_infra).text
        main_tf_content_initial = extract_code_block(response_core_infra, "main.tf", "hcl")
        variables_tf_content = extract_code_block(response_core_infra, "variables.tf", "hcl")

        if main_tf_content_initial and variables_tf_content:
            write_file("main.tf", main_tf_content_initial)
            write_file("variables.tf", variables_tf_content)
        else:
            print("Warning: Could not extract both main.tf and variables.tf from core infra response.")
            print("AI Response was:\n", response_core_infra)
            exit(1)
    except Exception as e:
        print(f"Error generating core infrastructure files: {e}")
        exit(1)

    # Step 4.4: Write src/index.js (hardcoded as per requirement and simplicity)
    write_file(
        "src/index.js",
        'exports.handler = async (event) => {\n  console.log("Lambda invoked with event:", JSON.stringify(event, null, 2));\n  return {\n    statusCode: 200,\n    headers: { "Content-Type": "application/json" },\n    body: JSON.stringify({ message: "My name is pankaj" }),\n  };\n};\n'
    )
    # Create a dummy package.json for npm install in GitHub Actions
    write_file(
        "src/package.json",
        '{\n  "name": "my-nodejs-app",\n  "version": "1.0.0",\n  "description": "A simple Node.js Lambda app",\n  "main": "index.js",\n  "scripts": {\n    "test": "echo \\"Error: no test specified\\" && exit 1"\n  },\n  "keywords": [],\n  "author": "",\n  "license": "ISC"\n}\n'
    )


    # Step 4.5: Generate updated main.tf with Lambda and ALB
    current_main_tf_content = ""
    if os.path.exists("main.tf"):
        with open("main.tf", "r") as f:
            current_main_tf_content = f.read()

    # Pass current main.tf as context to the AI for updating
    updated_main_tf_content = call_gemini_and_save(
        prompt_update_main_tf.format(current_main_tf_content=current_main_tf_content),
        "main.tf",
        "hcl"
    )
    if not updated_main_tf_content:
        print("Failed to generate updated main.tf. Exiting.")
        exit(1)


    # Step 4.6: Generate .github/workflows/deploy.yml
    github_actions_content = call_gemini_and_save(prompt_github_actions, ".github/workflows/deploy.yml", "yaml")
    if not github_actions_content:
        print("Failed to generate .github/workflows/deploy.yml. Exiting.")
        exit(1)

    # Step 4.7: Write .gitignore (hardcoded as per requirement)
    write_file(
        ".gitignore",
        ".env\nnode_modules/\nnpm-debug.log*\nyarn-debug.log*\nyarn-error.log*\n"
        ".terraform/\n*.tfstate*\n__pycache__/\nlambda.zip\n"
    )

    # Step 5: Initialize Git & Push
    print("\n--- Initializing Git repo and pushing to GitHub ---")
    if not os.path.isdir(".git"):
        if not run_terraform_command(["git", "init"]):
            print("Git init failed. Exiting.")
            exit(1)

    # Add all generated files
    if not run_terraform_command(["git", "add", "."]):
        print("Git add failed. Exiting.")
        exit(1)
    if not run_terraform_command(["git", "commit", "-m", "AI-generated Lambda deployment infra"]):
        print("Git commit failed. Exiting.")
        exit(1)
    if not run_terraform_command(["git", "branch", "-M", "main"]):
        print("Git branch failed. Exiting.")
        exit(1)

    # Set remote URL, handling if it already exists
    try:
        subprocess.run(["git", "remote", "set-url", "origin", GITHUB_REPO_URL], check=True, stderr=subprocess.PIPE)
        print(f"Git remote 'origin' set to {GITHUB_REPO_URL}")
    except subprocess.CalledProcessError as e:
        if "already exists" in e.stderr.decode():
            print("Git remote 'origin' already exists. Skipping 'add remote'.")
        else:
            print(f"Error setting git remote: {e.stderr.decode()}")
            exit(1)

    try:
        subprocess.run(["git", "push", "-u", "origin", "main"], check=True)
        print("Code pushed to GitHub. CI/CD will trigger now.")
    except subprocess.CalledProcessError as e:
        print(f"Error pushing to GitHub: {e.stderr.decode()}")
        print("Please ensure your GitHub repository exists, you have push access, and your Git credentials are configured correctly.")
        exit(1)

    print("\n--- Deployment Automation Script Finished ---")
    print("Please check your GitHub Actions workflow for deployment status.")
    print(f"\nYour S3 state bucket: {S3_STATE_BUCKET_NAME}")
    print(f"Your DynamoDB lock table: {DDB_LOCK_TABLE_NAME}")
    print(f"Your GitHub Repo: {GITHUB_REPO_URL}")

if __name__ == "__main__":
    main()