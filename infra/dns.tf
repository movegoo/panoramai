# ─── Route 53 DNS ─────────────────────────────────────────────────

data "aws_route53_zone" "main" {
  count = var.acm_certificate_arn != "" ? 1 : 0
  name  = "panoramai.mobsuccess.ai"
}

resource "aws_route53_record" "api" {
  count   = var.acm_certificate_arn != "" ? 1 : 0
  zone_id = data.aws_route53_zone.main[0].zone_id
  name    = "api.panoramai.mobsuccess.ai"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
