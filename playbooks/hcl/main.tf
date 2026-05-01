provider "aws" {
  region = "us-east-2"
}

data "aws_ami" "rhel9" {
  most_recent = true
  owners      = ["309956199498"] # Red Hat

  filter {
    name   = "name"
    values = ["RHEL-9*_HVM-*-x86_64-*"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

variable "vm_name" {
  type = string
}

variable "aws_key_name" {
  type = string
}

resource "aws_instance" "db" {
  ami           = data.aws_ami.rhel9.id
  instance_type = "t3.micro"
  key_name      = var.aws_key_name

  tags = {
    Name = var.vm_name
  }
}

output "db_vm_public_ip" {
  value = aws_instance.db.public_ip
}

output "db_vm_private_ip" {
  value = aws_instance.db.private_ip
}

output "db_vm_user" {
  value = "ec2-user"
}