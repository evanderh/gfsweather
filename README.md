# gfsweather

[demo](https://gfsweather.com)

![demo](https://github.com/evanderh/gfsweather/assets/3112477/17e4dce5-767b-4d1f-bc99-72910bd57830)

# build

build frontend production image

```
docker build -t gfsweather-frontend-prod -f frontend/Dockerfile.prod frontend/
```

run frontend prod image

```
docker run --rm -it -p 80:80 -v ./layers:/usr/share/nginx/html/layers gfsweather-frontend-prod
```
