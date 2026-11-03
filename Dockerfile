# Build stage: install the application and its locked dependencies into the
# system site-packages of the hardened Python builder image.
FROM registry.access.redhat.com/hi/python:3.15-builder@sha256:0f1e045db12ce181ff15ac036156225816394e2e76e3c87f51ff61596924f098 AS build
USER 0
WORKDIR /opt/app-root/src
COPY Pipfile Pipfile.lock pyproject.toml README.md LICENSE ./
COPY src/ ./src/
# pipenv is installed into an isolated prefix so that build tooling never
# lands in the site-packages that get copied into the runtime image.
# pipenv install --system --deploy reproduces the locked dependency set from
# Pipfile.lock; pipenv skips local file packages in --system mode, so the
# wordmill package itself is installed explicitly afterwards.
RUN pip install --no-cache-dir --target /opt/tools pipenv && \
    PYTHONPATH=/opt/tools python3 -m pipenv install --system --deploy && \
    pip install --no-cache-dir --no-deps . && \
    python3 -c "import importlib.util; assert importlib.util.find_spec('wordmill'), 'wordmill package failed to install'"

# Runtime stage: distroless Python image, no shell or package manager.
FROM registry.access.redhat.com/hi/python:3.15@sha256:a8241403eb7003db09cd13f0e0e1aad672c3d0bad0a39cf36d2b3c7ee7b70879
# The runtime image's sys.path includes /usr/local/lib/python3.12/site-packages
# but not /usr/local/lib64/..., so pure-Python and binary packages are both
# copied into that directory.
COPY --from=build --chown=65532:0 /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=build --chown=65532:0 /usr/local/lib64/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
ENV FLASK_APP="wordmill" \
    FLASK_RUN_HOST="0.0.0.0" \
    FLASK_RUN_PORT="8000"
EXPOSE 8000
USER 65532
ENTRYPOINT ["python3", "-m", "flask", "run"]
