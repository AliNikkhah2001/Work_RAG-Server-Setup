# Jenkinsfile — Work_RAG-Server-Setup Services Pipeline
# Runs on self-hosted Jenkins (root user, H200 server)
# Builds: LLM Manager, Gemma ×5, Embed ×3

pipeline {
    agent any

    environment {
        REGISTRY = 'local-h200:5000'
        DOCKERFILE_DIR = 'deploy/docker'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Lint') {
            steps {
                sh '''
                    set -e
                    echo "=== Running hadolint ==="
                    pip install hadolint 2>/dev/null || true
                    hadolint deploy/docker/Dockerfile.* || true
                '''
            }
        }

        stage('Build Docker Images') {
            steps {
                sh '''
                    set -e
                    echo "=== Building server-setup Docker images ==="
                    bash deploy/docker/build-all.sh ${REGISTRY}
                '''
            }
        }

        stage('Push to Local Registry') {
            steps {
                sh '''
                    set -e
                    echo "=== Pushing images to ${REGISTRY} ==="
                    docker push ${REGISTRY}/rag-manager:${TAG}
                    docker push ${REGISTRY}/rag-gemma:${TAG}
                    docker push ${REGISTRY}/rag-embed:${TAG}
                '''
            }
        }

        stage('Deploy to Dev (Alt Ports)') {
            when {
                branch 'develop'
            }
            steps {
                sh '''
                    set -e
                    echo "=== Deploying server-setup services to dev ==="
                    docker compose -f deploy/docker/docker-compose.test.yml down --remove-orphans 2>/dev/null || true
                    docker compose -f deploy/docker/docker-compose.test.yml up -d --build
                '''
            }
        }

        stage('Deploy to Production') {
            when {
                branch 'main'
            }
            steps {
                input message: 'Deploy server-setup services to production?', ok: 'Deploy'
                steps {
                    sh '''
                        set -e
                        echo "=== Deploying server-setup services to production ==="
                        docker compose -f deploy/docker/docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
                        docker compose -f deploy/docker/docker-compose.prod.yml up -d --build
                    '''
                }
            }
        }
    }

    post {
        always {
            sh 'docker system prune -f 2>/dev/null || true'
        }
    }
}
