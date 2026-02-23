# ─── S3 Bucket for GeoJSON cache ────────────────────────────────────
resource "aws_s3_bucket" "cache" {
  bucket        = "${local.name_prefix}-cache"
  force_destroy = var.env == "dev"

  tags = { Name = "${local.name_prefix}-cache" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cache" {
  bucket = aws_s3_bucket.cache.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "cache" {
  bucket = aws_s3_bucket.cache.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "cache" {
  bucket = aws_s3_bucket.cache.id
  versioning_configuration {
    status = "Suspended"
  }
}
