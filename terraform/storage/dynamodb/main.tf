resource "aws_dynamodb_table" "this" {
  for_each = var.tables

  name         = each.value.name
  billing_mode = each.value.billing_mode
  hash_key     = each.value.hash_key
  range_key    = each.value.range_key

  dynamic "attribute" {
    for_each = each.value.attributes
    content {
      name = attribute.value.name
      type = attribute.value.type
    }
  }

  tags = var.tags
}
