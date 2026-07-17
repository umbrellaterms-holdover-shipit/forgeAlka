#!/usr/bin/env bash

# Exit immediately if any command exits with a non-zero status
set -e

echo "=== Step 1: Updating system packages and installing prerequisites ==="
sudo apt-get update
sudo apt-get install -y curl gnupg ca-certificates

echo "=== Step 2: Downloading and adding the Elasticsearch Repository Key ==="
curl -fsSL https://artifacts.elastic.co/GPG-KEY-elasticsearch | sudo gpg --dearmor -o /usr/share/keyrings/elasticsearch-keyring.gpg

echo "=== Step 3: Registering the Elastic 8.x repository source ==="
echo "deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main" | sudo tee /etc/apt/sources.list.d/elastic-8.x.list

echo "=== Step 4: Refreshing repository indexes and installing components ==="
sudo apt-get update
sudo apt-get install -y elasticsearch nginx build-essential

echo "=== Installation complete! ==="