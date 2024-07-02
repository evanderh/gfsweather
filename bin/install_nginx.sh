#!/bin/bash

ENVIRONMENT=${ENV:-development}
echo "Running in $ENVIRONMENT environment"

CONF_FILENAME="nginx/gfsweather.conf"
NGINX_SITES_AVAILABLE="/etc/nginx/sites-available"
NGINX_SITES_ENABLED="/etc/nginx/sites-enabled"
STATIC_FOLDER="/var/www/gfsweather"
BUILD_FOLDER="./app/dist"
LAYERS_FOLDER="./layers"

# Check if Nginx directories exist
if [ ! -d "$NGINX_SITES_AVAILABLE" ] || [ ! -d "$NGINX_SITES_ENABLED" ]; then
    echo "Nginx directories not found. Make sure nginx is installed."
    exit 1
fi

echo "Copying $CONF_FILENAME to $NGINX_SITES_AVAILABLE"
sudo cp "$CONF_FILENAME" "$NGINX_SITES_AVAILABLE/$CONF_FILENAME"

echo "Enabling site by creating symbolic link to $NGINX_SITES_ENABLED/$CONF_FILENAME"
sudo ln -sf "$NGINX_SITES_AVAILABLE/$CONF_FILENAME" "$NGINX_SITES_ENABLED/$CONF_FILENAME"

echo "Creating static folder"
sudo mkdir -p "$STATIC_FOLDER"

if [ ! -d "$BUILD_FOLDER" ]; then
    echo "Build not found. Building..."
    cd app
    npm run build
    cd ..
fi

echo "Copying build"
sudo cp -r "$BUILD_FOLDER"/* "$STATIC_FOLDER"

if [ "$ENVIRONMENT" == "development" ]; then
    if [ ! -d "$STATIC_FOLDER/$LAYERS_FOLDER" ]; then
        echo "Copying layers"
        sudo cp -r "$LAYERS_FOLDER" "$STATIC_FOLDER"
    fi
else
    sudo mkdir -p "$STATIC_FOLDER/$LAYERS_FOLDER"
    sudo mount -t efs fs-02d8627a4bd3dc948.efs.us-east-1.amazonaws.com "$STATIC_FOLDER/layers"
fi

echo "Testing Nginx configuration..."
sudo nginx -t

echo "Reloading Nginx to apply changes..."
sudo systemctl reload nginx

if [ $? -ne 0 ]; then
    echo "Failed to reload Nginx. Please check the service status."
    exit 1
fi

echo "$CONF_FILENAME successfully installed and enabled."
