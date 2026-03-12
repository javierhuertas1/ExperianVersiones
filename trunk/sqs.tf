# =============================================================================
# SQS Configuration for Invoice Processing using EITS SQS Module
# =============================================================================

# Dead Letter Queue for Invoice Processing
module "invoice_processing_queue_dlq" {
  source = "git::https://code.experian.local/scm/EUCES/eits-tf-aws-sqs.git?ref=1.5.0"

  name                         = "${local.prefix}-invoice-processing-dlq"
  fifo_queue                   = true
  delay_seconds                = 0
  max_message_size             = 262144
  message_retention_seconds    = 1209600  # 14 days
  receive_wait_time_seconds    = 0
  visibility_timeout_seconds   = 300      # 5 minutes
  dead_letter_queue           = true      # Mark this as a DLQ
  
  # Use EITS module's built-in policy system
  policy_allowed_source_arns = [
    "arn:aws:lambda:${var.aws_region}:${local.account_id}:function:${local.prefix}-*"
  ]
}

# Main FIFO SQS Queue for Invoice Processing
module "invoice_processing_queue" {
  source = "git::https://code.experian.local/scm/EUCES/eits-tf-aws-sqs.git?ref=1.5.0"

  name                         = "${local.prefix}-invoice-processing-queue"
  fifo_queue                   = true
  delay_seconds                = 0
  max_message_size             = 262144
  message_retention_seconds    = 1209600  # 14 days
  receive_wait_time_seconds    = 0
  visibility_timeout_seconds   = 300      # 5 minutes
  
  # Use EITS module's built-in policy system
  policy_allowed_source_arns = [
    "arn:aws:lambda:${var.aws_region}:${local.account_id}:function:${local.prefix}-*"
  ]
  
  # Dead Letter Queue configuration using EITS module parameters
  dead_letter_queue_source = {
    main_queue = {
      sourceQueueArn  = module.invoice_processing_queue_dlq.queue_arn
      sourceQueueUrl  = module.invoice_processing_queue_dlq.queue_url
      maxReceiveCount = 5
    }
  }

  depends_on = [module.invoice_processing_queue_dlq]
}
