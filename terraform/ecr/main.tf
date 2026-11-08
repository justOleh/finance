# Container image repositories. Kept separate from the ECS module because
# images outlive compute: the ECS stack can be destroyed/recreated freely
# without losing pushed images.
resource "aws_ecr_repository" "this" {
  for_each = var.repositories

  name         = each.value.name
  force_delete = each.value.force_delete
  tags         = var.tags

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
      description  = "Keep only the ${each.value.keep_last_images} most recent images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = each.value.keep_last_images
      }
      action = { type = "expire" }
    }]
  })
}
