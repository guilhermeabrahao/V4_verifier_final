#!/usr/bin/env bash
# exit on error
set -o errexit

STORAGE_DIR=/opt/render/project/.render
CHROME_DIR=$STORAGE_DIR/chrome
CHROMEDRIVER_DIR=/usr/local/bin # Install chromedriver globally

# --- Instalar Google Chrome --- 
echo "Checking Chrome installation..."
if [[ ! -d $CHROME_DIR/opt/google/chrome ]]; then
  echo "...Downloading and installing Chrome"
  mkdir -p $CHROME_DIR
  cd $CHROME_DIR
  wget -q -P ./ https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  # Extract using ar and tar instead of dpkg -x to avoid potential EOF errors
  ar x ./google-chrome-stable_current_amd64.deb
  tar -xf data.tar.xz -C ./ 
  rm ./google-chrome-stable_current_amd64.deb control.tar.gz data.tar.xz debian-binary
  # Ensure the chrome binary is executable
  chmod +x $CHROME_DIR/opt/google/chrome/chrome
  cd $HOME/project/src # Return to project root or src
else
  echo "...Using Chrome from cache"
fi

# --- Instalar ChromeDriver (Método Atualizado) --- 
echo "Checking ChromeDriver installation..."
# Check if chromedriver exists and is executable
if [[ ! -x "$CHROMEDRIVER_DIR/chromedriver" ]]; then
  echo "...Downloading and installing ChromeDriver (using new method)"
  
  # Get installed Chrome full version (needed for new endpoint lookup)
  CHROME_FULL_VERSION=$($CHROME_DIR/opt/google/chrome/chrome --version | cut -d ' ' -f 3)
  if [[ -z "$CHROME_FULL_VERSION" ]]; then
    echo "Error: Could not determine Chrome full version." 
    exit 1
  fi
  echo "Detected Chrome full version: $CHROME_FULL_VERSION"
  
  # Fetch the last known good versions JSON data
  JSON_URL="https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
  echo "Fetching known good versions from $JSON_URL"
  
  # Try to find the exact version first, then fallback to major version if needed
  # Use awk to parse JSON and find the chromedriver URL for linux64
  CHROMEDRIVER_URL=$(wget -qO- $JSON_URL | awk -v version="$CHROME_FULL_VERSION" -F '"' '
    /"version":/ { current_version=$4 }
    current_version == version && /"platform": "linux64"/ && /"url":/ {
      for(i=1; i<=NF; i++) {
        if ($i == "url") {
          print $(i+2);
          exit;
        }
      }
    }
  ')

  # If exact version not found, try finding the latest for the major version (less reliable)
  if [[ -z "$CHROMEDRIVER_URL" ]]; then
      echo "Warning: Exact ChromeDriver version for $CHROME_FULL_VERSION not found in JSON. Trying latest stable..."
      CHROMEDRIVER_URL=$(wget -qO- $JSON_URL | awk -F '"' '
        /"Stable"/,/}/ { 
          if (/"chromedriver"/ && /"platform": "linux64"/ && /"url":/) {
            for(i=1; i<=NF; i++) {
              if ($i == "url") {
                stable_url = $(i+2);
              }
            }
          }
        }
        END { print stable_url }
      ')
  fi

  if [[ -z "$CHROMEDRIVER_URL" ]]; then
    echo "Error: Could not determine ChromeDriver download URL from JSON data."
    exit 1
  fi
  echo "Found ChromeDriver URL: $CHROMEDRIVER_URL"
  
  # Download and install ChromeDriver
  wget -q --continue -P /tmp "$CHROMEDRIVER_URL"
  unzip -o /tmp/chromedriver-linux64.zip -d $CHROMEDRIVER_DIR # Use -o to overwrite if exists
  # Adjust zip filename if the URL structure changes (it might include version)
  # Check the actual downloaded filename if unzip fails
  rm /tmp/chromedriver-linux64.zip 
  # Ensure chromedriver is executable
  chmod +x $CHROMEDRIVER_DIR/chromedriver
else
   echo "...Using ChromeDriver from cache or previous installation"
fi

# --- Instalar dependências Python --- 
echo "Installing Python dependencies..."
pip install --no-cache-dir pysqlite3-binary # Install this first for ChromaDB
pip install --no-cache-dir -r requirements.txt

# --- Fim do Script de Build --- 
echo "Build script finished."

