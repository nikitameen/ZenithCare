@echo off
echo Navigating to project directory...


ng build --configuration production
echo Building Docker image...
docker build -t gcr.io/hsphere/nodejs-frontend-v1 .

echo Build completed.

docker push gcr.io/hsphere/nodejs-frontend-v1  
echo docker pushed.
gcloud run deploy nodejs-frontend-v1 --image gcr.io/hsphere/nodejs-frontend-v1 --platform managed --allow-unauthenticated --project hsphere --region us-east1 --timeout=600s

pause