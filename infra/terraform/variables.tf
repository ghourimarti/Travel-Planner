variable "region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for all resources."
}

variable "project" {
  type        = string
  default     = "voyantra"
  description = "Name prefix + cost-allocation tag."
}

variable "env" {
  type        = string
  default     = "dev"
  description = "Environment (dev/staging/prod)."
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

# The single cost/resilience switch. dev=false (cheap), prod=true (HA).
# Controls: NAT-per-AZ, Multi-AZ RDS, a Redis replica, RDS deletion protection.
variable "highly_available" {
  type    = bool
  default = false
}

variable "cluster_version" {
  type    = string
  default = "1.31"
}

variable "node_instance_type" {
  type    = string
  default = "t3.large"
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 4
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}
