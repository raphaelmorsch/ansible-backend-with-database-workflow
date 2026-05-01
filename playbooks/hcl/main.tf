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

variable "ssh_allowed_cidr" {
  type    = string
  default = "0.0.0.0/0" # demo apenas
}

variable "postgres_allowed_cidr" {
  type    = string
  default = "0.0.0.0/0" # demo apenas
}

resource "aws_security_group" "db_sg" {
  name        = "${var.vm_name}-sg"
  description = "Allow SSH and PostgreSQL for demo"

  ingress {
    description = "SSH from AAP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  ingress {
    description = "PostgreSQL from OpenShift"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.postgres_allowed_cidr]
  }

  egress {
    description = "Allow outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name      = "${var.vm_name}-sg"
    ManagedBy = "Terraform"
  }
}

resource "aws_instance" "db" {
  ami           = data.aws_ami.rhel9.id
  instance_type = "t3.medium"
  key_name      = var.aws_key_name
  vpc_security_group_ids = [aws_security_group.db_sg.id]

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