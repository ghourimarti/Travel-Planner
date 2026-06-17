resource "aws_ecr_repository" "this" {
  for_each = toset(["api", "worker", "web"])

  name                 = "${local.name}/${each.key}"
  image_tag_mutability = "IMMUTABLE" # a tag always means one exact image — no silent re-pushes

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Keep image history bounded so storage cost doesn't grow forever.
resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "expire all but the 10 most recent images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
