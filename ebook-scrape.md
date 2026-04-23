
# HIRA 전자자료 수집 작업 지시서 

## step 1. ebook 목록 데이터 수집 

    https://www.hira.or.kr/ra/ebook/list.do?pgmid=HIRAA030402000000
    위 HIRA 전자자료 게시판에서 ebookList안의 메타 데이터 정보 (제목, 소관부서, 게시날짜, pdf 다운로드 url) 를 수집한다. 


    ebooklist 전자자료 목록 참고 
    ```
        <li>
            <div class="imgBox">
                <img src="/ebook/2026/03/BZ202603243124974.png" onerror="this.src='/images/ebook/noimg2.gif'" alt="KDRG-KM V2.2 분류집">
            </div>
            <div class="txtBox">
                <p class="tit">KDRG-KM V2.2 분류집</p>
                <span>분류체계개발부</span>
                <span>2026-03-24 10:44:34</span>
                
                    
                    
                        <a href="/ebooksc/2026/03/BZ202603243124987.pdf" class="btn_file">다운로드</a>   
                    
                
            </div>                     
        </li>
    ```

## step2. 파싱 대상 문서 선정 

    내가 육안으로 파악한 파싱 대상 문서는 다음과 같다. 

    https://www.hira.or.kr/ebooksc/2026/03/BZ202603233119206.pdf
    https://www.hira.or.kr/ebooksc/2026/03/BZ202603243124965.pdf
    https://www.hira.or.kr/ebooksc/2026/03/BZ202603243124987.pdf
    https://www.hira.or.kr/ebooksc/2026/03/BZ202603163084309.pdf
    https://www.hira.or.kr/ebooksc/2026/03/BZ202603053039374.pdf
    https://www.hira.or.kr/ebooksc/2026/03/BZ202603053039374.pdf
    https://www.hira.or.kr/ebooksc/2026/01/BZ202601272870642.pdf
    https://www.hira.or.kr/ebooksc/2026/01/BZ202601272870628.pdf
    https://www.hira.or.kr/ebooksc/2026/01/BZ202601272870622.pdf

    step 1. ebook 목록 데이터 수집 의 데이터를 가지고 2026년 기준 수집 가치가 있는 데이터 선별하고 파일 다운로드 받는다. 
    - 주기적으로 올라오는 내용 (연도마다 갱신 필요한 내용)
    - 코드나 업무 처리에 관한 내용 
    - 기타 제안 

    다운로드 받을 때 파일명은 제목에 맞춰서 적재 하고 
    다운로드 파이프라인 생성 (혹은 파이프라인 구성을 어떻게 해야 하는지)