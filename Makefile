processor:
	cd /home/lev0x/Documents/rinha-de-backend-2025/payment-processor && docker compose up -d

WORKERS ?= 250
test:
	cd /home/lev0x/Documents/rinha-de-backend-2025/rinha-test && K6_WEB_DASHBOARD=true k6 -e MAX_REQUESTS=$(WORKERS) run rinha.js