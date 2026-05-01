output "db_vm_public_ip" {
  value = aws_instance.db.public_ip
}

output "db_vm_private_ip" {
  value = aws_instance.db.private_ip
}

output "db_vm_user" {
  value = "ec2-user"
}