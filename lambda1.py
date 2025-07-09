import os
import random
import dotenv
import google.generativeai as genai
import textwrap
import re
import json
import subprocess
import uuid

# Load environment variables
dotenv.load_dotenv()

# Configure Google Generative AI
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
if not GOOGLE_API_KEY:
    print("Error: GOOGLE_API_KEY not found in .env file.")
    exit(1)
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

# Generation configuration for all AI calls
generation_config = genai.types.GenerationConfig(
    temperature=0.2,
)

# --- Global Constants (Adjust these as needed) ---
PROJECT_NAME = "pankaj-devops-lambda"
AWS_REGION = "ap-south-1"
LAMBDA_RUNTIME = "nodejs18.x"
GITHUB_REPO_URL = "https://github.com/pankajpachahara/automated_lambda1.git"  # Update this to your repo

# Generate a random hex suffix for unique bucket/table names
RANDOM_HEX = str(uuid.uuid4())[:8]

# Derived names for backend resources
S3_STATE_BUCKET_NAME = f"{PROJECT_NAME}-tfstate-{RANDOM_HEX}"
DDB_LOCK_TABLE_NAME = f"{PROJECT_NAME}-tf-lock-{RANDOM_HEX}"

# Define the literal string for S3 bucket interpolation for Gemini
S3_LAMBDA_CODE_BUCKET_TF_REF = "$${{aws_s3_bucket.lambda_code_bucket.id}}"


# --- Helper Functions ---
def run_terraform_command(command, directory):
    """Executes a Terraform command in the specified directory."""
    print(f"\n--- Running: {command} in {directory} ---")
    try:
        process = subprocess.run(
            command,
            cwd=directory,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Stdout:\n{process.stdout}")
        if process.stderr:
            print(f"Stderr:\n{process.stderr}")
        return process.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error during Terraform command: {command}")
        print(f"Stdout:\n{e.stdout}")
        print(f"Stderr:\n{e.stderr}")
        exit(1)
    except FileNotFoundError:
        print(f"Error: Command not found. Is Terraform installed and in your PATH?")
        exit(1)

def run_git_command(command, directory):
    """Executes a Git command in the specified directory."""
    print(f"\n--- Running: {' '.join(command)} in {directory} ---")
    try:
        process = subprocess.run(
            command,
            cwd=directory,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Stdout:\n{process.stdout}")
        if process.stderr:
            print(f"Stderr:\n{process.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error during Git command: {' '.join(command)}")
        print(f"Stdout:\n{e.stdout}")
        print(f"Stderr:\n{e.stderr}")
        return False

def write_file(path, content):
    """Helper to write content to a file, creating directories if needed."""
    try:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        print(f"Created {path}")
    except IOError as e:
        print(f"Error writing file {path}: {e}")
        exit(1)

def read_file(path):
    """Helper to read content from a file."""
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except IOError as e:
        print(f"Error reading file {path}: {e}")
        exit(1)

def extract_code_block(response, block_name, language):
    """Extracts a specific code block from the AI's response."""
    if block_name:
        pattern = re.compile(rf"^\s*###\s*{re.escape(block_name)}\s*{re.escape(language)}\s*\n```(?:{language})?\n(.*?)\n^\s*```", re.DOTALL | re.MULTILINE)
    else:
        pattern = re.compile(rf"```(?:{language})?\n(.*?)\n```", re.DOTALL)

    match = pattern.search(response)
    if match:
        return textwrap.dedent(match.group(1)).strip()
    return None

def extract_multiple_code_blocks(response, file_language_map):
    """
    Extracts multiple named code blocks from the AI's response based on a map.
    file_language_map = {
        "filename.ext": "language",
        "another_file.ext": "another_language"
    }
    """
    extracted_blocks = {}
    for filename, language in file_language_map.items():
        pattern = re.compile(rf"^\s*###\s*{re.escape(filename)}\s*{re.escape(language)}\s*\n```(?:{language})?\n(.*?)\n^\s*```", re.DOTALL | re.MULTILINE)
        match = pattern.search(response)
        if match:
            extracted_blocks[filename] = textwrap.dedent(match.group(1)).strip()
        else:
            print(f"Warning: Could not find code block for {filename} ({language}) in AI response.")
            extracted_blocks[filename] = None
    return extracted_blocks


# --- Prompts for Gemini ---

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
**Include Terraform output blocks for the S3 bucket name (named `terraform_state_bucket_name`) and the DynamoDB table name (named `terraform_lock_table_name`).**
Output must be in this exact format:
### backend-bootstrap/backend.tf hcl
```hcl
# Terraform code goes here
```
"""

# Prompt 2: Core Infrastructure (VPC, Subnets, Security Groups, IAM)
prompt_core_infra = f"""
You are an expert DevOps engineer.
Generate the initial Terraform configuration for main.tf and variables.tf files.
These files should define:

A new AWS VPC with CIDR block "10.0.0.0/16".

Two public subnets in different availability zones.

An Internet Gateway and route table associations.

A security group for the Lambda function (allowing inbound from ALB).

A security group for the ALB (allowing HTTP inbound from anywhere).

IAM role and policy for the Lambda function with basic execution permissions (CloudWatch logs, ENI management for VPC).

An S3 bucket for storing the Lambda deployment package (e.g., {PROJECT_NAME}-lambda-code-${{data.aws_caller_identity.current.account_id}}).

The main.tf should also contain the Terraform backend configuration, referencing the S3 bucket {S3_STATE_BUCKET_NAME} and DynamoDB table {DDB_LOCK_TABLE_NAME} created in the previous step.

Variables for aws_region (default: {AWS_REGION}), project_name (default: {PROJECT_NAME}), and environment (default: development).

Ensure no Lambda or ALB resources are defined yet, only the networking, security, and IAM components.

Include a data source for aws_caller_identity to get the account ID.

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

# Prompt 3: Update main.tf with Lambda and ALB
prompt_update_main_tf = f"""
You are an expert DevOps engineer.
Here is the current content of my main.tf file:

```hcl
{{current_main_tf_content}}
```

Please update this main.tf file to include the AWS Lambda function and the Application Load Balancer (ALB).

For the Lambda function:

Name: {PROJECT_NAME}-nodejs-app

Handler: index.handler

Runtime: {LAMBDA_RUNTIME}

Timeout: 30 seconds, Memory: 128 MB

It should run in the VPC, use the IAM role defined previously, and be associated with the Lambda security group.

The code will be uploaded to the S3 bucket '{S3_LAMBDA_CODE_BUCKET_TF_REF}' with key 'lambda.zip'.

Include a source_code_hash (even if placeholder, as GitHub Actions will update it).

For the ALB:

Name: {PROJECT_NAME}-alb

Type: application load balancer, internet-facing.

Security group should be the one defined previously.

Subnets: the public subnets defined previously.

Create a target group (lambda_tg) of type lambda that targets the Lambda function.

Create an HTTP listener on port 80 that forwards traffic to this target group.

Grant the ALB permission to invoke the Lambda function using aws_lambda_permission.

Add an alb_dns_name output.

Output the complete, updated main.tf file content in the following format:

### main.tf hcl
```hcl
# Updated main.tf code goes here
```

### src/index.js javascript
```javascript
// Node.js Lambda code
```

### src/package.json json
```json
// package.json for Node.js Lambda
```
"""

# Prompt 4: GitHub Actions Workflow
prompt_github_actions = f"""
You are an expert DevOps engineer.
Generate the GitHub Actions workflow file for .github/workflows/deploy.yml.
This workflow should:

Trigger on push to the main branch.

Use ubuntu-latest as the runner.

Define necessary permissions for OIDC to assume an AWS role (id-token: write, contents: read).

Set up Node.js (v18.x).

Install Node.js dependencies (e.g., npm install in src/).

Package the Node.js application from src/ into a lambda.zip file. The src directory contains index.js. Use zip -r lambda.zip . from inside the src directory.

Set up Terraform using hashicorp/setup-terraform@v2.

Configure AWS credentials using OIDC for an IAM role named arn:aws:iam::${{{{ secrets.AWS_ACCOUNT_ID }}}}:role/GitHubActionsRoleForDeployment.

Run terraform init (ensuring it uses the S3 backend and DynamoDB lock table, region {AWS_REGION}).

Run terraform plan.

Run terraform apply -auto-approve.

The lambda.zip file should be uploaded to the S3 bucket created by Terraform (you can use aws s3 cp or ensure Terraform's aws_lambda_function resource uploads it from the local path). Ensure the Lambda source_code_hash is updated dynamically during packaging.

Output must be in this exact format:

### .github/workflows/deploy.yml yaml
```yaml
# GitHub Actions workflow code goes here
```
"""

# --- Main Script Execution ---
def main():
    # Step 1: Load .env (already done at the top)
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("GEMINI_API_KEY not found. Please check your .env file and ensure it contains GOOGLE_API_KEY=YOUR_KEY.")
        exit(1)

    # Step 2: Configure Gemini (already done at top)

    # Step 3: Create all necessary directories upfront
    print("Creating project directories...")
    os.makedirs(".github/workflows", exist_ok=True)
    os.makedirs("backend-bootstrap", exist_ok=True)
    os.makedirs("src", exist_ok=True)
    print("Directories created.")

    # Step 4.1: Generate backend-bootstrap/backend.tf
    # Step 4.1: Generate backend-bootstrap/backend.tf
    backend_tf_content = extract_code_block(model.generate_content(prompt_backend, generation_config=generation_config).text, "backend-bootstrap/backend.tf", "hcl")

    # Step 4.2: Run Terraform init + apply for backend only
    print("\n--- Running Terraform backend init/apply ---")

    if not run_terraform_command("terraform init", directory="backend-bootstrap"):
        print("Terraform backend init failed. Exiting.")
        exit(1)

    if not run_terraform_command("terraform apply -auto-approve", directory="backend-bootstrap"):
        print("Terraform backend apply failed. Exiting.")
        exit(1)
    print("Terraform backend setup complete. S3 bucket and DynamoDB table for state have been created.")

    # Step 4.3: Generate initial main.tf and variables.tf
    print("\n--- Sending prompt for main.tf and variables.tf (initial infrastructure) ---")
    try:
        response_core_infra = model.generate_content(prompt_core_infra, generation_config=generation_config).text
        extracted_infra_blocks = extract_multiple_code_blocks(
            response_core_infra,
            {
                "main.tf": "hcl",
                "variables.tf": "hcl"
            }
        )

        main_tf_content_initial = extracted_infra_blocks.get("main.tf")
        variables_tf_content = extracted_infra_blocks.get("variables.tf")

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

    # Step 4.4: Write src/index.js and package.json (initial hardcoded)
    write_file(
        "src/index.js",
        'exports.handler = async (event) => {\n  console.log("Lambda invoked with event:", JSON.stringify(event, null, 2));\n  return {\n    statusCode: 200,\n    headers: { "Content-Type": "application/json" },\n    body: JSON.stringify({ message: "My name is pankaj" }),\n  };\n};\n'
    )
    write_file(
        "src/package.json",
        '{\n  "name": "my-nodejs-app",\n  "version": "1.0.0",\n  "description": "A simple Node.js Lambda app",\n  "main": "index.js",\n  "scripts": {\n    "test": "echo \\"Error: no test specified\\" && exit 1"\n  },\n  "keywords": [],\n  "author": "",\n  "license": "ISC"\n}\n'
    )

    # Step 4.5: Generate updated main.tf with Lambda and ALB (and new src files)
    print("\n--- Sending prompt for main.tf, src/index.js, src/package.json (Lambda & ALB) ---")
    current_main_tf_content = ""
    if os.path.exists("main.tf"):
        current_main_tf_content = read_file("main.tf")

    try:
        response_lambda_api = model.generate_content(
            prompt_update_main_tf.format(current_main_tf_content=current_main_tf_content),
            generation_config=generation_config,
        ).text

        extracted_lambda_blocks = extract_multiple_code_blocks(
            response_lambda_api,
            {
                "main.tf": "hcl",
                "src/index.js": "javascript",
                "src/package.json": "json"
            }
        )

        updated_main_tf_content = extracted_lambda_blocks.get("main.tf")
        lambda_index_js_content = extracted_lambda_blocks.get("src/index.js")
        lambda_package_json_content = extracted_lambda_blocks.get("src/package.json")

        if updated_main_tf_content:
            write_file("main.tf", updated_main_tf_content)
        else:
            print("Error: Could not extract updated main.tf content for Lambda/ALB. Keeping existing main.tf.")

        if lambda_index_js_content:
            write_file("src/index.js", lambda_index_js_content)
        else:
            print("Warning: Could not extract src/index.js content. Using placeholder.")

        if lambda_package_json_content:
            write_file("src/package.json", lambda_package_json_content)
        else:
            print("Warning: Could not extract src/package.json content. Using placeholder.")

    except Exception as e:
        print(f"An error occurred during Lambda/ALB prompt generation: {e}")
        exit(1)

    print("Lambda function, ALB configuration, and source files generated/updated.")

    # Step 4.6: Generate .github/workflows/deploy.yml
    print("\n--- Generating GitHub Actions workflow ---")
    try:
        response = model.generate_content(prompt_github_actions, generation_config=generation_config).text
        github_actions_content = extract_code_block(response, ".github/workflows/deploy.yml", "yaml")
        if github_actions_content:
            write_file(".github/workflows/deploy.yml", github_actions_content)
        else:
            print("Failed to generate .github/workflows/deploy.yml. Exiting.")
            exit(1)
    except Exception as e:
        print(f"Error generating GitHub Actions workflow: {e}")
        exit(1)

    # Step 4.7: Write .gitignore (hardcoded as per requirement)
    write_file(
        ".gitignore",
        ".env\nnode_modules/\nnpm-debug.log*\nyarn-debug.log*\nyarn-error.log*\n"
        ".terraform/\n*.tfstate*\n__pycache__/\nlambda.zip\n"
    )

    # --- Git Initialization and Push ---
    print("\n--- Initializing Git repo and pushing to GitHub ---")

    # Initialize git if not already initialized
    if not os.path.isdir(".git"):
        try:
            subprocess.run(["git", "init"], check=True, cwd=os.getcwd())
            print("Git repository initialized.")
        except subprocess.CalledProcessError as e:
            print(f"Error initializing git: {e}")
            exit(1)

    # Add remote
    try:
        # Check if origin remote already exists
        subprocess.run(["git", "remote", "get-url", "origin"], check=True, capture_output=True, text=True)
        # If it exists, set URL
        subprocess.run(["git", "remote", "set-url", "origin", GITHUB_REPO_URL], check=True, cwd=os.getcwd())
        print(f"Git remote 'origin' set to {GITHUB_REPO_URL}")
    except subprocess.CalledProcessError:
        # If it doesn't exist, add it
        subprocess.run(["git", "remote", "add", "origin", GITHUB_REPO_URL], check=True, cwd=os.getcwd())
        print(f"Git remote 'origin' added as {GITHUB_REPO_URL}")

    # Git operations
    if not run_git_command(["git", "add", "."], directory=os.getcwd()):
        print("Git add failed. Exiting.")
        exit(1)
    if not run_git_command(["git", "commit", "-m", "AI-generated Lambda deployment infra"], directory=os.getcwd()):
        print("Git commit failed. Exiting.")
        exit(1)
    if not run_git_command(["git", "branch", "-M", "main"], directory=os.getcwd()):
        print("Git branch failed. Exiting.")
        exit(1)

    try:
        subprocess.run(["git", "push", "-u", "origin", "main"], check=True, cwd=os.getcwd())
        print("Code pushed to GitHub. CI/CD will trigger now.")
    except subprocess.CalledProcessError as e:
        print(f"Error pushing to GitHub: {e}")
        print("Please ensure your GitHub repository exists, you have push access, and your Git credentials are configured correctly.")
        exit(1)

    print("\n--- Deployment Automation Script Finished ---")
    print("Please check your GitHub Actions workflow for deployment status.")
    print(f"\nYour S3 state bucket: {S3_STATE_BUCKET_NAME}")
    print(f"Your DynamoDB lock table: {DDB_LOCK_TABLE_NAME}")
    print(f"Your GitHub Repo: {GITHUB_REPO_URL}")

if __name__ == "__main__":
    main()