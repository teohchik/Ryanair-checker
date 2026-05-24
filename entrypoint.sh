#!/bin/sh
set -e
mkdir -p data
alembic upgrade head
exec python -m app
