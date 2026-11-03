resource "aws_ecr_repository" "this" {
  for_each = var.repositories

  name                 = each.value
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  tags                 = var.tags

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each = var.repositories

  repository = aws_ecr_repository.this[each.key].name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last ${var.keep_last_images} images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = var.keep_last_images
      }
      action = { type = "expire" }
    }]
  })
}
