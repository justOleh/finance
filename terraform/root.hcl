# Root terragrunt configuration
# This file is inherited by all child terragrunt.hcl files

locals {
    # Parse root directory to determine environment and project
    root_dir = get_terragrunt_dir()
}

# Configure Terragrunt to automatically store tfstate files in an S3 bucket
remote_state {
    backend = "s3"
    config = {
        bucket         = "my-finance-tfstate"
        key            = "${path_relative_to_include()}/terraform.tfstate"
        region         = "us-east-1"
        encrypt        = true
        dynamodb_table = "terraform-locks"
    }
}

# Prevent accidental destruction of production infrastructure
prevent_destroy = false

# Require specific Terraform version
terraform_version_constraint = "~> 1.2"

# Require specific Terragrunt version
terragrunt_version_constraint = "~> 0.40"