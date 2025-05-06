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

# --- Instalar ChromeDriver --- 
echo "Checking ChromeDriver installation..."
# Check if chromedriver exists and is executable
if [[ ! -x "$CHROMEDRIVER_DIR/chromedriver" ]]; then
  echo "...Downloading and installing ChromeDriver"
  # Get installed Chrome version
  CHROME_VERSION=$($CHROME_DIR/opt/google/chrome/chrome --version | cut -d ' ' -f 3 | cut -d '.' -f 1)
  if [[ -z "$CHROME_VERSION" ]]; then
    echo "Error: Could not determine Chrome version." 
    exit 1
  fi
  echo "Detected Chrome version: $CHROME_VERSION"
  
  # Get the latest ChromeDriver version for the detected Chrome version
  CHROMEDRIVER_VERSION=$(wget -qO- https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION})
  if [[ -z "$CHROMEDRIVER_VERSION" ]]; then
    echo "Error: Could not determine ChromeDriver version for Chrome $CHROME_VERSION."
    # Fallback to a recent known version if lookup fails (optional)
    # CHROMEDRIVER_VERSION="114.0.5735.90" # Example fallback
    # echo "Warning: Falling back to ChromeDriver version $CHROMEDRIVER_VERSION"
    exit 1
  fi
  echo "Downloading ChromeDriver version: $CHROMEDRIVER_VERSION"
  
  # Download and install ChromeDriver
  wget -q --continue -P /tmp "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip"
  unzip -o /tmp/chromedriver_linux64.zip -d $CHROMEDRIVER_DIR # Use -o to overwrite if exists
  rm /tmp/chromedriver_linux64.zip
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

