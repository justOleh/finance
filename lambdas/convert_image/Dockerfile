# Lambda "convert image" (ADR-013). Build context: lambdas/convert_image/
#   docker build --platform linux/arm64 --provenance=false -t <repo>:latest .
# --provenance=false: Lambda rejects the attestation manifests buildx adds by default.
# boto3 is already part of the Lambda base image.
FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r requirements.txt

COPY convert_image/ ${LAMBDA_TASK_ROOT}/convert_image/

CMD ["convert_image.handler.lambda_handler"]
