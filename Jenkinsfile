pipeline {

    agent any

    environment {
        IMAGE_NAME = "idrisniyi94/cardgame"
        IMAGE_TAG = "${BUILD_NUMBER}"
        DOCKERHUB_CREDENTIALS = credentials('ab8f8dd3-42e0-4d7d-87c5-4950c6145d6c')
    }

    stages {

        stage("Init Clean Log") {
            steps {
                sh "echo '' > full-build.log"
            }
        }

        stage("Docker Login") {
            steps {
                sh "echo $DOCKERHUB_CREDENTIALS_PSW | docker login -u $DOCKERHUB_CREDENTIALS_USR --password-stdin | tee -a full-build.log"
            }
        }

        stage("Build Docker Image") {
            steps {
                sh "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} . | tee -a full-build.log"
            }
        }

        stage("Scan Docker Image with Trivy") {
            steps {
                sh '''
                if [ ! -f html.tpl ]; then
                  curl -sSL -o html.tpl https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/html.tpl
                fi

                trivy image --exit-code 1 --severity CRITICAL,HIGH ${IMAGE_NAME}:${IMAGE_TAG} \
                  --format template \
                  --template "@./html.tpl" \
                  --output trivy-report.html | tee -a full-build.log
                '''
            }
        }

        stage("Publish Trivy Docker Report") {
            steps {
                publishHTML([
                    allowMissing: false,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: '.',
                    reportFiles: 'trivy-report.html',
                    reportName: 'Trivy Docker Image Report'
                ])
            }
        }

        stage("Update Kubernetes Deployment") {
            steps {
                sh "sed -i 's|image:.*|image: ${IMAGE_NAME}:${IMAGE_TAG}|' k8s/deployment.yaml | tee -a full-build.log"
            }
        }

        stage("Scan Kubernetes Config with Trivy") {
            steps {
                sh '''
                if [ ! -f html.tpl ]; then
                  curl -sSL -o html.tpl https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/html.tpl
                fi

                trivy config --exit-code 1 --severity CRITICAL,HIGH ./k8s \
                  --format template \
                  --template "@./html.tpl" \
                  --output kubernetes-trivy-report.html | tee -a full-build.log
                '''
            }
        }

        stage("Publish Trivy Kubernetes Report") {
            steps {
                publishHTML([
                    allowMissing: false,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: '.',
                    reportFiles: 'kubernetes-trivy-report.html',
                    reportName: 'Trivy Kubernetes Config Report'
                ])
            }
        }

        stage("Deploy to Kubernetes") {
            steps {
                withCredentials([file(credentialsId: '7e2fc12c-558d-4521-8060-6c51e976793c', variable: 'KUBECONFIG')]) {
                    sh '''
                    echo "🚀 Deploying to Kubernetes..." | tee -a full-build.log
                    kubectl apply -f k8s/ | tee -a full-build.log
                    // kubectl rollout status deployment/card-game -n lab-server | tee -a full-build.log
                    '''
                }
            }
        }

        // Always run AI Agent Log Analysis, even if previous stages fail
        stage("AI Agent Log Analysis") {
            when {
                expression { true }
            }
            steps {
                catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
                    sh '''
                    echo "📤 Sending full build log to AI Agent..."

                    curl -X POST http://67.167.244.232:4999/analyze/ \
                         -F "log=@full-build.log;type=text/plain" \
                         -o ai-report.html \
                         -H "Content-Type: multipart/form-data" | tee -a full-build.log
                    echo "AI Agent analysis complete. Report saved as ai-report.html" | tee -a full-build.log
                    '''
                }
            }
        }

        stage("Publish AI Agent Report") {
            steps {
                publishHTML([
                    allowMissing: false,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: '.',
                    reportFiles: 'ai-report.html',
                    reportName: 'AI Agent Build Log Analysis'
                ])
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'full-build.log'
        }
    }
    options {
        timestamps()
        disableConcurrentBuilds()
    }
}
