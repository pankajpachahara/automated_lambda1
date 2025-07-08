import os
import subprocess
import time
from openai import OpenAI
from dotenv import load_dotenv

# Step 1: Load .env
load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    print("❌ API key not found. Check .env file.")
    exit()

# Step 2: Initialize OpenRouter Client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

# Step 3: Define Prompt
prompt = """
Requirement:
Use Terraform to deploy a Node.js app to AWS Lambda using GitHub Actions (CI/CD pipeline). The pipeline should:
- Create an S3 bucket and DynamoDB table for backend tfstate locking
- Package & deploy Node.js app to AWS Lambda
- Expose it via ALB URL (with target group & listener)
- Create all required infra like IAM, Security Groups, Subnets, VPC
- Generate GitHub workflow (deploy.yml) with `terraform init`, `plan`, `apply` on push to main
- Create variables.tf and use best practices
- Prevent .env from being pushed
- Automate the whole setup including folders and file generation
"""

print("🔁 Sending prompt to OpenRouter...")

# Step 4: Call OpenRouter
try:
    response = client.chat.completions.create(
        model="openai/gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
        max_tokens= 3500,
    )
    reply = response.choices[0].message.content
    print("✅ AI response received.")
except Exception as e:
    print("❌ Error while getting AI response:", e)
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
        print(f"✅ Created {path}")

# Step 6: Terraform init + apply for backend only
print("⚙️ Running Terraform backend init/apply...")
os.chdir("backend-bootstrap")
subprocess.run(["terraform", "init"])
subprocess.run(["terraform", "apply", "-auto-approve"])
os.chdir("..")

# Step 7: Initialize Git & Push
print("📦 Initializing Git repo...")
if not os.path.isdir(".git"):
    subprocess.run(["git", "init"])

subprocess.run(["git", "add", "."])
subprocess.run(["git", "commit", "-m", "AI-generated Lambda deployment infra"])
subprocess.run(["git", "branch", "-M", "main"])

# Replace this with your GitHub repo
GIT_REMOTE = "https://github.com/pankajpachahara/automated_lambda.git"

subprocess.run(["git", "remote", "add", "origin", GIT_REMOTE])
subprocess.run(["git", "push", "-u", "origin", "main"])

print("🚀 All done! CI/CD will trigger from GitHub.")
