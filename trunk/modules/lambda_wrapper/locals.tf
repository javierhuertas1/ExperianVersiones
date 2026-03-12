locals {
    zip_path = data.archive_file.package_lambda.output_path
    # Use filebase64sha256 for more stable hash calculation
    source_code_hash = filebase64sha256(data.archive_file.package_lambda.output_path)
}

