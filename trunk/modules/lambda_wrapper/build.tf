data "archive_file" "package_lambda" {
  type        = "zip"
  output_path = "${path.module}/.build/${var.function_scope}.zip"
  excludes = [
    "__pycache__/**",
    "*.pyc",
    ".pytest_cache/**",
    "tests/**"
  ]

  # Main lambda source files
  dynamic "source" {
    for_each = fileset(var.source_dir, "**")
    content {
      content  = file("${var.source_dir}/${source.value}")
      filename = source.value
    }
  }
}