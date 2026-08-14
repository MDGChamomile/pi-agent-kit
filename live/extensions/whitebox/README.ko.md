# Pi Whitebox

[English](README.md)

Whitebox는 낯선 프로젝트의 테스트·빌드·스크립트를 엄격한 오프라인 Bubblewrap 경계 안에서 실행하는 Linux 전용 Pi 확장 기능입니다.

모델이 작업 방법을 스스로 선택하게 두면서, 프로젝트 명령 실행과 Pi 파일 도구에는 단단한 경계만 적용합니다.

## 보호 경계

Whitebox 모드에서는:

- `whitebox_run` 명령에 현재 Git 작업공간만 읽기·쓰기로 제공합니다.
- 루트 `.git` 폴더는 읽기 전용입니다.
- 격리된 명령은 인터넷, 실제 홈 폴더, Pi 세션, 인증정보, 기존 환경변수에 접근할 수 없습니다.
- Pi의 `read`, `write`, `edit`, `grep`, `find`, `ls` 도구는 작업공간 안으로 제한됩니다.
- 호스트 Bash와 사용자 `!`·`!!` 명령은 차단됩니다.
- 실행 시간, 출력 크기, 동시 실행을 제한합니다.
- 시작 검사나 도구 소유권 확인이 실패하면 안전하게 차단합니다.

Whitebox가 격리하는 대상은 프로젝트 명령과 위 여섯 파일 도구입니다. Pi 프로세스 전체, 모델 통신, 명시적으로 추가한 다른 확장 기능, 쓰기 가능한 프로젝트 자체를 격리하는 것은 아닙니다.

중요한 미저장 파일이 없는 재생성 가능한 프로젝트 사본에서 사용하세요. 강한 악성 코드나 자원 고갈 공격에는 별도 가상 컴퓨터를 사용해야 합니다.

## 요구사항

- Linux
- Node.js 22.19 이상
- Pi coding agent 0.84.2에서 검증
- `/usr/bin/bwrap`과 `/usr/bin/flock`
- `/usr/bin` 아래의 `bash`, `python3`, `git`, `make`, `cc`, `c++`
- 실제 `.git` 폴더가 있는 일반 Git 저장소 루트; worktree는 지원하지 않음
- 비특권 사용자 네임스페이스 활성화

현재 Node.js 22.22.3, Pi 0.84.2, Bubblewrap 0.9.0, Linux 6.8에서 테스트했습니다.

## 체크아웃에서 설치

```bash
git clone https://github.com/MDGChamomile/pi-agent-kit.git
cd pi-agent-kit/live/extensions/whitebox
npm install
npm link
```

이 명령은 `piw` 실행기를 설치합니다. Pi 명령은 미리 `PATH`에서 실행 가능해야 합니다.

## 실행

검사할 일회용 프로젝트의 루트에서 실행합니다.

```bash
cd /path/to/project
piw
```

`piw`는 의도적으로 Whitebox만 불러옵니다.

```text
pi --no-extensions -e <whitebox>/index.ts --no-skills --no-approve --whitebox
```

추가 인자는 Pi로 전달됩니다. 다른 확장 기능을 명시적으로 불러오면 그 확장 기능은 호스트 권한으로 실행되므로 신뢰 경계가 넓어집니다.

## 적합한 작업

- 테스트, 빌드, 린트, 프로젝트 스크립트
- 프로젝트에 이미 준비된 Node.js·Python 도구
- `git status`, `git diff`, `git log` 같은 읽기 전용 Git 확인

지원하지 않는 작업:

- 인터넷 접근과 패키지 다운로드
- 호스트 인증정보가 필요한 명령
- 대화형 프로그램
- commit, merge, rebase, fetch, pull, push 같은 Git 변경

명령별 기본 제한은 120초, 최대 제한은 900초입니다. 캡처 출력은 10MiB로 제한됩니다.

## 보안상 한계

- 작업공간은 쓰기 가능하므로 내부 파일이 손상되거나 삭제될 수 있습니다.
- 프로젝트의 `AGENTS.md`는 Pi가 계속 읽을 수 있습니다. `--no-context-files`는 전역 지침도 함께 끄므로 보호 범위를 이해할 때만 사용하세요.
- 지원 도구 실행을 위해 `/usr`의 읽기 전용 런타임 파일과 `/etc`의 일부 신원·런타임 파일이 보입니다.
- CPU, 메모리, 작업공간 디스크 고갈을 완전히 통제하지 않습니다.
- Whitebox는 위험을 줄이지만 독립적으로 격리된 호스트를 대체하지 않습니다.

## 테스트

```bash
npm test
```

테스트는 임시 Git 작업공간을 만들고 파일시스템, 네트워크, 환경변수, 네임스페이스, 실행 수명, 파일 도구, 실제 Pi 진입점 경계를 확인합니다. 외부 프로젝트 코드는 실행하지 않습니다.

## 라이선스

MIT
