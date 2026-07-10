@echo off
REM admeta-hub 주간 파이프라인 — Windows 작업 스케줄러가 매주 실행.
REM crawl -> extract -> build(map+DB). 로그는 backend\data\weekly.log 에 누적.
cd /d C:\Users\ParkEunJin\admeta-hub\backend
set PYTHONIOENCODING=utf-8
echo ---------------------------------------------- >> data\weekly.log
py -3 -m admeta.pipeline >> data\weekly.log 2>&1
REM 정적 사이트(web\index.html) 재생성 후 push -> GitHub Pages 자동 배포
py -3 ..\scripts\build_web.py >> data\weekly.log 2>&1
cd /d C:\Users\ParkEunJin\admeta-hub
git add web\index.html >> backend\data\weekly.log 2>&1
git commit -m "weekly: 지표 사전 자동 갱신" >> backend\data\weekly.log 2>&1
git push origin master >> backend\data\weekly.log 2>&1
