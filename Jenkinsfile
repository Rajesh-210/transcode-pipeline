pipeline {
    agent any

    environment {
        DOCKERHUB_USER = 'chilukurir'
        DOCKERHUB_CREDENTIALS_ID = 'dockerhub-credentials'
        API_IMAGE = "${DOCKERHUB_USER}/transcode-api"
        WORKER_IMAGE = "${DOCKERHUB_USER}/transcode-worker"
        IMAGE_TAG = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                echo "Checking out code from Git..."
                checkout scm
            }
        }

        stage('Code Lint & Test') {
            steps {
                echo "Running code analysis and syntax checks..."
                sh '''
                    python3 -m py_compile app/main.py app/worker.py app/api/v1/router.py
                    echo "Python syntax verification passed."
                '''
            }
        }

        stage('Build Docker Images') {
            steps {
                echo "Building Docker container images with tag ${IMAGE_TAG} and latest..."
                sh '''
                    docker build --no-cache -t ${API_IMAGE}:${IMAGE_TAG} -t ${API_IMAGE}:latest -f docker/api.Dockerfile .
                    docker build -t ${WORKER_IMAGE}:${IMAGE_TAG} -t ${WORKER_IMAGE}:latest -f docker/worker.Dockerfile .
                '''
            }
        }

        stage('Push to Docker Hub') {
            steps {
                echo "Authenticating and pushing images to Docker Hub..."
                withCredentials([usernamePassword(credentialsId: "${DOCKERHUB_CREDENTIALS_ID}", usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
                    sh '''
                        echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin
                        docker push ${API_IMAGE}:${IMAGE_TAG}
                        docker push ${API_IMAGE}:latest
                        docker push ${WORKER_IMAGE}:${IMAGE_TAG}
                        docker push ${WORKER_IMAGE}:latest
                        docker logout
                    '''
                }
            }
        }

        stage('Deploy to EC2') {
            steps {
                echo "Deploying application containers on EC2..."
                sh '''
                    export DOCKERHUB_USER=${DOCKERHUB_USER}
                    export IMAGE_TAG=${IMAGE_TAG}
                    docker compose -f docker-compose.prod.yml pull
                    docker compose -f docker-compose.prod.yml down --remove-orphans || true
                    docker compose -f docker-compose.prod.yml up -d
                '''
            }
        }

        stage('Smoke Test / Health Check') {
            steps {
                echo "Waiting for services to become healthy..."
                sleep time: 10, unit: 'SECONDS'
                sh '''
                    for i in $(seq 1 10); do
                        if curl -s http://localhost:8000/healthz | grep -q "healthy"; then
                            echo "API Health Check Passed!"
                            exit 0
                        fi
                        echo "Waiting for API to be ready (attempt $i/10)..."
                        sleep 3
                    done
                    echo "API Health Check Failed!"
                    docker compose -f docker-compose.prod.yml logs api
                    exit 1
                '''
            }
        }
    }

    post {
        always {
            echo "Pipeline execution completed."
            sh 'docker image prune -f || true'
        }
        success {
            echo "Transcode Pipeline successfully built, tested, and deployed to EC2!"
        }
        failure {
            echo "Deployment failed. Check Jenkins console logs."
        }
    }
}
