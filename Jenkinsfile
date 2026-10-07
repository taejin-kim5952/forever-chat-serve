// 지식LAB(openapi-chat-serve) 배포 파이프라인.
//
// ### 전제
//
//   - Jenkins 가 개발 서버와 같은 장비에서 돌고, `jenkins` 계정이 docker 를 쓸 수 있다
//   - 배포 폴더가 `/opt/chat-serve` 다. **`/root` 아래면 안 된다** — `/root` 는 `dr-xr-x---`
//     라서 `jenkins` 계정이 들어갈 수 없고, 아래 '준비 확인'이 거기서 멈춘다
//     (2026-10-07 에 실제로 `/root/chatapp` 에 있어서 옮겼다)
//   - 그 폴더에 `.env` · `models/bge-m3-onnx` · `packs/` 가 **미리** 있다
//
// ### 이미지에 모델을 굽지 않는다
//
// 임베딩 모델 565MB 는 저장소에 없다(`.gitignore` 의 `models/`). 서버에 한 번 받아 두고
// 볼륨으로 물린다(`:ro`) — 모델은 거의 바뀌지 않으니 코드를 고칠 때마다 565MB 를 주고받을
// 이유가 없다. 폐쇄망 납품만 이미지에 굽는다(`--build-arg WITH_MODEL=true`).
//
// ### 자료(`packs/`)는 이 파이프라인이 건드리지 않는다 ★
//
// **검수는 운영에서 쌓인다.** 배포가 자료를 덮으면 서버에서 승인한 QA 가 PC 것으로 바뀌고,
// 누가 누구를 덮었는지 아무도 모르게 된다. 자료를 바꿀 때는 사람이 `scp` 로 올리고
// 색인한다(`scripts/pack_index.py` 또는 관리자 화면의 재색인 버튼).
//
// 그래서 이 파이프라인은 **색인도 하지 않는다.** 코드를 고쳤다고 벡터를 다시 만들 이유가
// 없고, 자료가 많아지면 몇 분씩 걸려 배포가 그만큼 길어진다.
pipeline {
    agent any

    options {
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 25, unit: 'MINUTES')
    }

    environment {
        APP        = 'openapi-chat-serve'
        IMAGE      = 'openapi-chat-serve'
        HOST_PORT  = '18100'

        // 자료·설정·모델이 있는 곳. 이미지에 없는 것은 전부 여기서 온다.
        DEPLOY_DIR = '/opt/chat-serve'

        HEALTH_URL = 'http://localhost:18100/health/ready'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                sh 'git --no-pager log -1 --pretty=format:"배포 대상 커밋: %h %s (%an)"'
            }
        }

        stage('준비 확인') {
            // 없는 채로 띄우면 컨테이너는 멀쩡히 뜨고 **모든 질문이 미해결로 떨어진다.**
            // 오류가 안 나는 종류라 여기서 먼저 막는다.
            steps {
                sh '''
                    set -e
                    if [ ! -f "$DEPLOY_DIR/models/bge-m3-onnx/model.onnx" ]; then
                        echo "$DEPLOY_DIR/models/bge-m3-onnx/model.onnx 가 없습니다."
                        echo "모델을 서버에 한 번 받아 두세요 — docs/11-배포.md 의"
                        echo "'모델을 서버에 한 번 받아 두기'. 파일 이름이 model.onnx 여야 합니다"
                        echo "(허깅페이스 원본 이름은 model_quantized.onnx 입니다)."
                        exit 1
                    fi
                    if [ ! -f "$DEPLOY_DIR/.env" ]; then
                        echo "$DEPLOY_DIR/.env 가 없습니다. .env.server.example 을 복사해 채우세요."
                        exit 1
                    fi
                    if ! grep -q "^ADMIN_PASSWORD=." "$DEPLOY_DIR/.env"; then
                        echo "$DEPLOY_DIR/.env 의 ADMIN_PASSWORD 가 비어 있습니다."
                        exit 1
                    fi
                    mkdir -p "$DEPLOY_DIR/data" "$DEPLOY_DIR/packs" "$DEPLOY_DIR/var"
                    echo "준비 확인 완료"
                '''
            }
        }

        stage('Build image') {
            steps {
                // 빌드 번호로 태그를 남긴다. 되돌릴 때 어느 이미지로 갈지 고를 수 있어야 한다.
                sh '''
                    set -e
                    docker build -t "$IMAGE:$BUILD_NUMBER" -t "$IMAGE:latest" .
                    docker images "$IMAGE" | head -4
                '''
            }
        }

        stage('Deploy') {
            steps {
                // 지금 도는 컨테이너가 어느 이미지였는지 적어 둔다. 실패하면 이것으로 되돌린다.
                sh '''
                    set -e
                    docker inspect --format '{{.Config.Image}}' "$APP" > .prev_image 2>/dev/null || echo "" > .prev_image
                    echo "이전 이미지: $(cat .prev_image)"

                    docker rm -f "$APP" 2>/dev/null || true

                    # 볼륨 넷. data/packs/var 를 빼면 서버에서 **프로젝트가 0개**가 되고,
                    # models 를 빼면 모든 질문이 미해결이 된다. 모델만 읽기 전용이다.
                    docker run -d \
                        --name "$APP" \
                        --restart unless-stopped \
                        -p "$HOST_PORT":18100 \
                        -e TZ=Asia/Seoul \
                        --env-file "$DEPLOY_DIR/.env" \
                        -v "$DEPLOY_DIR/data":/app/data \
                        -v "$DEPLOY_DIR/packs":/app/packs \
                        -v "$DEPLOY_DIR/var":/app/var \
                        -v "$DEPLOY_DIR/models/bge-m3-onnx":/app/models/bge-m3-onnx:ro \
                        "$IMAGE:$BUILD_NUMBER"

                    docker ps --filter "name=$APP" --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
                '''
            }
        }

        stage('기동 확인') {
            steps {
                // 모델(565MB)을 올리고 Chroma 를 여는 데 몇 초 걸린다.
                //
                // `status` 가 아니라 **`embed_model`** 로 판정한다. studio 모드는 승인된 QA 가
                // 0건이어도 `status: ok` 를 내기 때문이다(QA 를 만드는 곳이라 그게 정상이다).
                // 그래서 status 만 보면 모델이 없는 것도 통과해 버린다.
                sh '''
                    set -e
                    for i in $(seq 1 24); do
                        BODY=$(curl -sf "$HEALTH_URL" || true)
                        case "$BODY" in
                            *'"embed_model":"ok"'*)
                                echo "기동 확인 (${i}회차)"
                                echo "$BODY"
                                case "$BODY" in
                                    *'"qa_serving":0'*)
                                        echo "경고: 내보낼 수 있는 QA 가 0건입니다."
                                        echo "      자료를 올린 뒤 색인하지 않았을 수 있습니다:"
                                        echo "      docker exec $APP python scripts/pack_index.py packs/<프로젝트>"
                                        ;;
                                esac
                                exit 0
                                ;;
                            *'"embed_model":"missing'*)
                                echo "모델 볼륨이 붙지 않았습니다:"
                                echo "$BODY"
                                exit 1
                                ;;
                        esac
                        echo "기동 대기 중... (${i}/24)"
                        sleep 5
                    done
                    echo "기동 실패: $HEALTH_URL 가 120초 안에 응답하지 않았습니다."
                    docker logs --tail 100 "$APP" || true
                    exit 1
                '''
            }
        }

        stage('묵은 이미지 정리') {
            steps {
                sh '''
                    docker images "$IMAGE" --format '{{.Tag}} {{.ID}}' \
                        | grep -v latest \
                        | sort -k1 -n -r \
                        | tail -n +6 \
                        | awk '{print $2}' \
                        | xargs -r docker rmi -f 2>/dev/null || true
                    docker image prune -f >/dev/null 2>&1 || true
                '''
            }
        }
    }

    post {
        failure {
            sh '''
                PREV=$(cat .prev_image 2>/dev/null || echo "")
                if [ -n "$PREV" ]; then
                    echo "배포 실패 — 이전 이미지로 롤백합니다: $PREV"
                    docker rm -f "$APP" 2>/dev/null || true
                    docker run -d \
                        --name "$APP" \
                        --restart unless-stopped \
                        -p "$HOST_PORT":18100 \
                        -e TZ=Asia/Seoul \
                        --env-file "$DEPLOY_DIR/.env" \
                        -v "$DEPLOY_DIR/data":/app/data \
                        -v "$DEPLOY_DIR/packs":/app/packs \
                        -v "$DEPLOY_DIR/var":/app/var \
                        -v "$DEPLOY_DIR/models/bge-m3-onnx":/app/models/bge-m3-onnx:ro \
                        "$PREV"
                else
                    echo "롤백할 이전 이미지가 없습니다(최초 배포이거나 빌드 단계에서 실패)."
                fi
                docker logs --tail 200 "$APP" 2>/dev/null || true
            '''
        }
    }
}
