provider "aws" {
  region = "us-east-2"
}

resource "aws_instance" "db" {
  ami           = "ami-0c02fb55956c7d316"
  instance_type = "t3.micro"

  tags = {
    Name = "demo-db"
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