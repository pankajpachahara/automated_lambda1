import os
import subprocess
import time
from dotenv import load_dotenv
import google.generativeai as genai

# Step 1: Load .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("GEMINI_API_KEY not found. Please check your .env file.")
    exit()

# Step 2: Configure Gemini
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-pro')

# Step 3: Define Prompt
prompt = """
You are an expert DevOps engineer.
Based on the following requirement,
generate all necessary files in properly fenced code blocks with appropriate language tags like hcl, js, yaml etc.

## Requirement:
Use Terraform and GitHub Actions to automate deployment of a Node.js app to AWS Lambda.
- Create an S3 bucket and DynamoDB table to store the Terraform state and lock it
- Create a VPC, public subnets, security groups, IAM roles and policies
- Deploy the Node.js app as AWS Lambda function
- Create an Application Load Balancer (ALB) that routes HTTP traffic to Lambda
- Create a GitHub Actions workflow (.github/workflows/deploy.yml) to:
  - Install dependencies
  - Package the Node.js app into lambda.zip
  - Run Terraform init/plan/apply on push to main
- Ensure .env is excluded using .gitignore
- Organize the files in appropriate folders:
  - backend-bootstrap/backend.tf
  - main.tf and variables.tf in root
  - index.js in src/ to return "My name is pankaj"
  - .github/workflows/deploy.yml
  - .gitignore

Each section must be output in this format:
### backend-bootstrap/backend.tf hcl
<code>
"""

print("Sending prompt to Gemini...")

# Step 4: Call Gemini
try:
    response = model.generate_content(prompt)
    reply = response.text
    print("AI response received.")
except Exception as e:
    print("Error while getting Gemini response:", e)
    exit()

# Step 5: Create folders and files
os.makedirs(".github/workflows", exist_ok=True)
os.makedirs("backend-bootstrap", exist_ok=True)

files = {
    "backend-bootstrap/backend.tf": reply.split("```hcl")[1].split("```")[0].strip() if "backend.tf" in reply else "",
    "main.tf": reply.split("```hcl")[2].split("```")[0].strip() if "main.tf" in reply else "",
    "variables.tf": reply.split("```hcl")[3].split("```")[0].strip() if "variables.tf" in reply else "",
    "index.js": 'exports.handler = async (event) => {\n  return {\n    statusCode: 200,\n    body: "My name is Pankaj",\n  };\n};\n',
    ".github/workflows/deploy.yml": reply.split("```yaml")[1].split("```")[0].strip() if "deploy.yml" in reply else "",
    ".gitignore": ".env\n*.zip\n__pycache__/\nterraform.tfstate*\n.terraform/\n",
}

for path, content in files.items():
    with open(path, "w") as f:
        f.write(content)
        print(f"Created {path}")

# Step 6: Terraform init + apply for backend only
print("Running Terraform backend init/apply...")
os.chdir("backend-bootstrap")
subprocess.run(["terraform", "init"])
subprocess.run(["terraform", "apply", "-auto-approve"])
os.chdir("..")

# Step 7: Initialize Git & Push
print("Initializing Git repo...")
if not os.path.isdir(".git"):
    subprocess.run(["git", "init"])

subprocess.run(["git", "add", "."])
subprocess.run(["git", "commit", "-m", "AI-generated Lambda deployment infra"])
subprocess.run(["git", "branch", "-M", "main"])

GIT_REMOTE = "https://github.com/pankajpachahara/automated_lambda.git"
subprocess.run(["git", "remote", "remove", "origin"], stderr=subprocess.DEVNULL)
subprocess.run(["git", "remote", "add", "origin", GIT_REMOTE])
subprocess.run(["git", "push", "-u", "origin", "main"])

print("CI/CD will trigger from GitHub.")
