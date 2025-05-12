#!/bin/bash

rm -f data-ingestion-suite/projects.json
docker compose -f data-ingestion-suite/docker/engine-only/docker-compose-engine.yml --project-directory ./ -p dt4h-tofhir up -d --wait
