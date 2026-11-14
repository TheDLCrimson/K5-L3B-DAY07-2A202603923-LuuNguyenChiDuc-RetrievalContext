# Báo cáo Day 7 - Agentic RAG trên Luật Đất đai 2013 và 2024

Lưu Nguyễn Chí Đức (2A202603923), lớp L3B.
Repo: <https://github.com/TheDLCrimson/K5-L3B-DAY07-2A202603923-LuuNguyenChiDuc-RetrievalContext>.
Chi tiết từng thí nghiệm, giả thuyết viết trước khi chạy và kết quả: [EXPERIMENTS.md](../../EXPERIMENTS.md); cách chạy: [src/README.md](../../src/README.md).

## Dữ liệu và benchmark

- **Nguồn, quyền sử dụng, số trang và số chunk:** Luật Đất đai 2013 (45/2013/QH13) và Luật Đất đai 2024 (31/2024/QH15), bản Công báo chính thức, 4 file PDF, 370 trang nội dung, lấy nguyên từ lab Day 6 ([data/day6/README.md](../../data/day6/README.md)).
  Văn bản quy phạm pháp luật không thuộc đối tượng bảo hộ quyền tác giả (Luật Sở hữu trí tuệ, Điều 15 khoản 2), nên bản xuất 1.264 chunk được commit trong [data/day6/chunks.json](../../data/day6/chunks.json).
  Chunk là chiến lược B của Day 6 (theo điều, nếu dài thì theo nhóm khoản, tối đa 1.000 ký tự); 237 chunk vắt qua ranh giới trang.
- **Vector store, embedding model, phiên bản và số chiều:** PostgreSQL 16 + pgvector 0.8.7 trong container Day 6 (`docker compose -p day6_student_starter`), tìm kiếm cosine chính xác (không dùng ANN), filter `year` trong SQL.
  Embedding `intfloat/multilingual-e5-base`, revision `d128750`, 768 chiều; passage có tiền tố `passage:`, query có tiền tố `query:` (mỗi tiền tố kèm một dấu cách).
  Kết nối được kiểm tra khi chạy: đúng 1.264 hàng, đúng model và số chiều; bản xuất khớp từng chunk với `B.jsonl` của Day 6 (ID, nội dung, trang, hash) và một chunk nhúng lại cho cosine 1,0 với vector đã lưu ([export_info.json](../../data/day6/export_info.json)).
  Dense và hybrid ở Lab 7 cho đúng kết quả của cấu hình C và D ở Day 6 trên cùng 30 câu, nên đây đúng là index Day 6.
- **Agent model, cách chạy và phân chia dev/test:** `anthropic/claude-haiku-5.5` qua OpenRouter, dùng lại lớp provider của lab Day 4 ([src/providers.py](../../src/providers.py)); chọn model rẻ nhất có tool calling, chi phí thật do OpenRouter báo.
  Benchmark ([benchmark/README.md](../../benchmark/README.md)) có 46 câu: dev 30 câu có đáp án + 3 câu thiếu bằng chứng, test 10 + 3.
  Dev là toàn bộ 30 câu của Day 6 (dev, test đã xem và holdout), vì đã đọc cả nên chỉ dùng để chỉnh; test là 13 câu mới, viết và commit trước mọi lần chạy Lab 7, không có điều luật nào trùng với gold của dev.
- **Cách xác định câu có/thiếu evidence và tiêu chí chấm:** câu có đáp án ghi `gold` là danh sách evidence thay thế `{source_id, page, evidence}`; bộ kiểm tra [src/verify_benchmark.py](../../src/verify_benchmark.py) xác nhận 56/56 evidence nằm trong một chunk.
  Một chunk "trúng" khi đúng nguồn, khoảng trang của chunk chứa trang gold và chứa trọn câu trích (quy tắc của Day 6, vì starter đòi trang bắt đầu trùng trang gold sẽ chấm trượt các chunk vắt trang).
  Câu thiếu bằng chứng gần chủ đề (số liệu do tỉnh hoặc nghị định quy định, thuế suất, lệ phí) và mỗi câu ghi từ khóa đã tìm trên toàn bộ 1.264 chunk cùng số chunk khớp; bộ kiểm tra báo lỗi nếu số này thay đổi.
  Kết luận "không có trong corpus" dựa trên tìm kiếm toàn bộ, không dựa vào top-k.
  Filter `year` chỉ được đặt khi chính câu hỏi nêu phiên bản luật, và bộ kiểm tra bắt buộc điều đó, nên filter đến từ người dùng chứ không từ gold.

## Retrieval và thử nghiệm

Context budget là 3.300 ký tự mỗi kết quả, tính cả nhãn nguồn, chọn trước khi chạy: luôn chứa đủ 3 chunk dài nhất của Day 6 (budget 800 của starter loại phần lớn chunk).
Mọi phương pháp tìm trên cùng 1.264 chunk, cùng filter của câu hỏi, cùng câu hỏi gốc không viết lại; luôn xuất top 3.
Context Evidence Rate trong bảng này là top 3 đóng gói vào budget, nên bằng Evidence Hit@3; của agent ở bảng sau.

| Cấu hình | Phương pháp, top-k, filter, rerank, context budget | Giả thuyết / thay đổi | Split | Hit@1 | Evidence Hit@3 | Context Evidence Rate | Thời gian / chi phí |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline (M1) | Dense e5 trên pgvector, top 3, filter `year`, 3.300 ký tự | Mạnh với câu diễn đạt lại; trượt ở khoản lân cận | dev | 21/30 (70%) | 26/30 (87%) | 26/30 | 42 ms/câu, $0 |
| Phương pháp 2 (M2) | BM25 (k1 1,5, b 0,75) trên âm tiết + cặp âm tiết | Ngang dense với câu đúng từ luật, kém với câu diễn đạt lại | dev | 20/30 (67%) | 23/30 (77%) | 23/30 | 15 ms, $0 |
| Phương pháp 3 (M3) | Hybrid: top 20 mỗi bên, min-max theo câu, 0,7 dense + 0,3 BM25 (RRF k 60: 23/30, 25/30) | Hit@1 cao hơn dense | dev | 24/30 (80%) | 27/30 (90%) | 27/30 | 61 ms, $0 |
| Cải thiện 1 (M4) | Hợp top 20 hai bên (tối đa 40), rerank `BAAI/bge-reranker-v2-m3` fp32 | Sửa các lỗi khoản lân cận h05, h06, h10 | dev | 26/30 (87%) | 28/30 (93%) | 28/30 | 3,6 s (lần chạy đầu ở E1: 4,0 s), $0 (GPU GTX 1650) |
| Cải thiện 2 (M4 pool 10) | Như M4, top 10 mỗi bên | Giảm khoảng nửa thời gian, Hit@3 giữ trong 1 câu | dev | 26/30 (87%) | 27/30 (90%) | 27/30 | 2,2 s (chạy cùng phiên với M4), $0 |
| Cấu hình đã chọn | M4 pool 10 | Chốt trên dev trước khi chạy test | test | 9/10 (90%) | 10/10 (100%) | 10/10 | 1,8 s, $0 |
| Baseline | M1 dense | | test | 7/10 (70%) | 8/10 (80%) | 8/10 | 37 ms, $0 |

Không cộng điểm thô của hai retriever: hybrid chỉ cộng điểm đã chuẩn hóa min-max hoặc hạng (RRF), rerank xếp theo một điểm của cross-encoder.
fp16 được thử trước và chậm hơn khoảng 5 lần trên GTX 1650 (16,9 s/câu), nên rerank chạy fp32.
Quy tắc chọn retrieval viết trước khi chạy: Hit@3 cao nhất, trong vòng 1 câu thì Hit@1, rồi thời gian; M4 thắng ở bước 2 (Hit@1 26 so với 24).

**Hai lỗi dev, nguyên nhân, cách thử và lý do chọn cấu hình:**

1. h05 "Đất ở thì có bị giới hạn thời gian sử dụng không?" (câu không nêu phiên bản luật, gold ở cả Điều 125 Luật 2013 và Điều 171 Luật 2024).
   Dense và hybrid lấy Điều 172 ngay sau Điều 171 (đất có thời hạn); rerank đưa Điều 171 Luật 2024 lên hạng 3.
   Trong agent A1, các lượt tìm của mô hình chỉ đưa về Điều 125 Luật 2013; lượt `year=2024` bị chặn vì câu hỏi không nêu năm, nên câu trả lời chỉ theo Luật 2013 (đã hết hiệu lực): điểm 1.
   Thay đổi A3: cho phép tìm riêng từng phiên bản khi câu hỏi không nêu phiên bản (vẫn chặn năm trái với phiên bản câu hỏi nêu); sau đó h05 trích cả hai luật (điểm 2) và tỷ lệ trích đủ hai luật tăng từ 12/13 lên 13/13, không có trích dẫn sai phiên bản.
2. h06 "Hai bên tranh chấp đất đều đã có sổ đỏ thì phải mang vụ việc ra cơ quan nào?" và h03: gold ở hạng 4 với M4 (h06: Điều 235 về hòa giải và các khoản khác của Điều 203, 236 xếp trước Điều 203 khoản 1).
   Trong agent, lượt tìm thứ hai viết bằng thuật ngữ của luật đưa đúng khoản vào context: Context Evidence Rate của mọi agent trên dev là 30/30, so với 26-28/30 của một lượt tìm bằng câu hỏi gốc.
3. Lỗi trích dẫn: A0 q08 được thấy chunk 0225 (Điều 81 khoản 9, bất khả kháng) nhưng lại trích 0224; A4 h10 viết nhầm mã `cb363-0149` cho chunk `cb365-0149` mà nó được thấy, bị bộ kiểm tra citation loại.
   Cả hai cho thấy ID tồn tại chưa chứng minh nguồn hỗ trợ, nên citation được chấm bằng cách đọc.

Cấu hình agent được chọn trên dev theo quy tắc viết trước khi chấm nhãn (E3): (1) 3/3 từ chối đúng và không từ chối nhầm nhiều hơn A0; (2) điểm grounded answer trung bình cao nhất, chênh dưới 0,05 coi như hòa; (3) tỷ lệ citation hỗ trợ cao hơn; (4) thời gian, chi phí.
Cả năm cấu hình hòa ở bước 2; A4 thắng ở bước 3 (70/70 citation hỗ trợ) và được chốt trong [selection.json](../../results/agent/selection.json) trước khi chạy test.

## Agent và đánh giá

- **Tool, số lượt gọi, điều kiện dừng, cách chọn context và xử lý lỗi:** agent tự viết ([src/agent.py](../../src/agent.py)) có hai tool: `search_law(query, year?)` trả tối đa 3 chunk mới trong budget 3.300 ký tự (chunk đã thấy chỉ được liệt kê, không gửi lại), và `finish(status, answer, citations)`.
  Dừng khi gọi `finish`, hoặc sau 6 lượt gọi model (khi đó từ chối với lý do `turn_limit`); lượt tìm thứ 5 trở đi bị từ chối kèm lời nhắc gọi `finish`.
  Kiểm tra bằng code: `year` phải khớp câu hỏi (mô hình đã đặt năm câu hỏi không nêu 12 lần trên dev A0/A1 và đều bị chặn); citation chỉ hợp lệ nếu chunk đã được trả về trong lần chạy, ID sai bị loại và ghi lại, câu trả lời không còn citation hợp lệ thành từ chối.
  Lỗi provider hoặc retrieval kết thúc lần chạy với trạng thái `error` và thông điệp, không thử lại ngầm, không thay bằng kết quả giả; trên mọi lần chạy dev và test không có lỗi.
  System prompt chỉ có quy tắc chung, không có ví dụ lấy từ câu nào của benchmark; nội dung chunk được coi là dữ liệu, không phải chỉ dẫn.

| Cấu hình / split | Tool use | Số lượt gọi (1 / 2 / 3 / 4 lượt mỗi câu) | Grounded answer 0/1/2 và trung bình | Citation hợp lệ | Câu có citation | Abstention đúng | Từ chối nhầm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A0 dense / dev | 33/33 | 52 (21 / 7 / 3 / 2) | 0 / 0 / 30, 2,00 | 69/71 | 30/30 | 3/3 | 0/30 |
| A1 rerank / dev | 33/33 | 49 (22 / 8 / 1 / 2) | 0 / 1 / 29, 1,97 | 74/75 | 30/30 | 3/3 | 0/30 |
| A3 tìm theo phiên bản / dev | 33/33 | 57 (13 / 17 / 2 / 1) | 0 / 1 / 29, 1,97 | 83/84 | 30/30 | 3/3 | 0/30 |
| A4 rerank pool 10 / dev | 33/33 | 46 (23 / 7 / 3 / 0) | 0 / 0 / 30, 2,00 | 70/70 | 30/30 | 3/3 | 0/30 |
| A5 (A3 + A4) / dev | 33/33 | 60 (15 / 13 / 1 / 4) | 0 / 1 / 29, 1,97 | 84/85 | 30/30 | 3/3 | 0/30 |
| A0 dense (baseline) / test | 13/13 | 29 (5 / 3 / 2 / 3) | 0 / 0 / 10, 2,00 | 32/33 | 10/10 | 3/3 | 0/10 |
| A4 (đã chọn) / test | 13/13 | 28 (5 / 3 / 3 / 2) | 2 / 0 / 8, 1,60 | 40/41 | 9/9 | 2/3 | 1/10 |

Context grade trên 10 câu test có đáp án: A0 có 10 câu mức 2; A4 có 9 câu mức 2 và 1 câu mức 0 (t07).

| Query ID | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do |
| --- | --- | --- | --- | --- |
| t04 (A4) | Có đáp án, điều kiện | 1 lượt `search_law(year=2024)`; Điều 158 khoản 5 và 6 ở top 3 | Tối thiểu 03 thửa đất cùng mục đích, tương đồng, đã chuyển nhượng hoặc trúng đấu giá [cb365-0255], cách tính [cb365-0252] | Đáp án 2, context 2, 2/2 citation hỗ trợ |
| tu01 (A0) | Thiếu bằng chứng | 2 lượt; chỉ có Điều 159, 257 về thẩm quyền và thời điểm áp dụng bảng giá đất | Từ chối nêu giá đường Nguyễn Huệ, chỉ ra bảng giá do UBND TP. Hồ Chí Minh ban hành, nằm ngoài corpus | Từ chối đúng, 3/3 citation hỗ trợ |
| t07 (A4) | Có đáp án, lỗi | 2 lượt; lượt 1 không có Điều 188 khoản 3, lượt 2 tìm Điều 168 rồi dừng | Trả lời thời điểm được thực hiện quyền (Điều 168) thay vì thời điểm có hiệu lực, nói không tìm thấy | Đáp án 0, context 0; A0 tìm lại bằng thuật ngữ của luật và trả lời đúng |
| t10 (A4) | Có đáp án, từ chối nhầm | Lượt 1 đã trả về Điều 179 khoản 3 | Trích nguyên văn "mỗi lần thuê không quá 10 năm" nhưng vẫn từ chối vì luật ghi "sản xuất nông nghiệp", câu hỏi ghi "trồng trọt" | Đáp án 0 (từ chối câu có đáp án), context 2 |
| tu02 (A4) | Thiếu bằng chứng | 4 lượt | Từ chối nêu tỷ lệ lệ phí trước bạ, nhưng nói Điều 190 miễn lệ phí cho "chuyển nhượng" đất nông nghiệp trong xã; điều này nói về chuyển đổi | Từ chối nhưng thêm khẳng định sai: chấm không đúng; citation 0411 không hỗ trợ |
| h05 (A1, dev) | Có đáp án | Lượt `year=2024` bị chặn | Chỉ trả lời theo Luật 2013 | Đáp án 1; A3 sửa thành 2 |

- **Đường dẫn trace, nhãn, lệnh chạy, thời gian và chi phí:** trace retrieval ở [results/retrieval/](../../results/retrieval/); trace agent (prompt, tool, từng lượt gọi model với token, chi phí, thời gian, từng tool call với tham số và kết quả, context cuối, câu trả lời) ở [results/agent/](../../results/agent/).
  Nhãn ở `reviews.json` của từng cấu hình, mỗi nhãn có lý do; test có thêm [review_labels.csv](../../results/agent/test/review_labels.csv) và `context_grades.json`; số liệu tổng hợp bằng `starter/agent_metrics.py` ở `agent_metrics.json`.
  Lệnh: `python -m src.eval_retrieval --split dev`, `python -m src.run_agent --split dev --config A4_rerank_pool10`, test thêm `--final`; đầy đủ ở [src/README.md](../../src/README.md).
  Chi phí model cho toàn bộ dev và test 0,233 USD (tổng `cost_usd` trong các trace dev và test, do OpenRouter báo); một câu khoảng 0,001-0,002 USD, 5-12 giây (trung vị).
- **Kết quả trước/sau, ví dụ lỗi, đánh đổi và giới hạn:**
  - Rerank cải thiện retrieval rõ nhất (dev Hit@1 21 → 26, test Hit@3 8 → 10), đổi lấy khoảng 2-4 giây mỗi lượt tìm; pool 10 giảm 40% thời gian tìm mà gần như giữ chất lượng.
  - Tìm theo phiên bản (A3) sửa lỗi chỉ trả lời một luật, đổi lấy nhiều lượt tìm hơn (57 so với 49) và thời gian 11,6 giây trung vị.
  - Trên test, cấu hình đã chọn kém hơn baseline (1,60 so với 2,00); mọi khác biệt đều do cách mô hình viết query, lúc dừng tìm và mức thận trọng, không do phương pháp retrieval, vì một lượt tìm bằng câu hỏi gốc của A4 đạt 10/10.
    Trên dev năm cấu hình hòa trong 0,05 và bước phân định theo tỷ lệ citation chỉ cách nhau vài citation, nên lựa chọn trên dev không đáng tin với 30 câu dev, 10 câu test và mỗi cấu hình chạy một lần.
  - Abstention vững: 3/3 ở mọi cấu hình dev, 5/6 trên test; lần sai từ chối đúng nhưng thêm khẳng định sai.

## Kết luận, nguồn và giới hạn

- **Kết luận:** agent nhiều lượt tìm đưa được evidence vào context nhiều hơn một lượt tìm bằng câu hỏi gốc (dev 30/30 so với 26-28/30), và kiểm tra citation, năm bằng code ngăn được lỗi mà prompt không ngăn được.
  Không có cấu hình agent nào tốt hơn rõ ràng: phần lớn sai số đến từ hành vi của mô hình giữa các lần chạy, nên bước tiếp theo nên là chạy lặp nhiều lần mỗi cấu hình và mở rộng test.
- **Nguồn:** văn bản luật từ vbpl.vn (đường dẫn và SHA-256 trong manifest Day 6); model `intfloat/multilingual-e5-base` và `BAAI/bge-reranker-v2-m3` (revision ghi trong code); agent `anthropic/claude-haiku-5.5` qua OpenRouter.
- **Giới hạn:**
  - Cùng một người viết câu hỏi, đáp án và gold, có tra corpus khi viết, nên benchmark nghiêng về các khoản dễ tìm bằng từ khóa; test chỉ 10 câu có đáp án (một câu là 10 điểm phần trăm).
  - Mỗi cấu hình chạy một lần; không đo phương sai giữa các lần chạy, trong khi các khác biệt quan sát được nằm trong phạm vi đó.
  - Nhãn dev và test được soạn với sự hỗ trợ của AI bằng cách đọc từng câu trả lời với từng chunk trong context, sau đó tôi kiểm tra lại; câu thiếu bằng chứng được kiểm tra bằng tìm từ khóa, có thể sót cách diễn đạt khác.
  - Luật 2013 đã hết hiệu lực từ 01/01/2025 nhưng vẫn trong corpus theo thiết kế Day 6; agent nêu cả hai luật khi câu hỏi không chỉ rõ phiên bản, nhưng không tự cảnh báo luật nào còn hiệu lực.
  - Rerank cần GPU để có thời gian chấp nhận được (4 s/lượt trên GTX 1650).

## Thử thách nâng cao (nếu thực hiện)

Không thực hiện.

## Sử dụng AI

| Loại sử dụng | Nội dung |
| --- | --- |
| Soạn thảo | AI (Claude Code) viết nháp code, tài liệu và các câu hỏi test mới theo kế hoạch tôi duyệt; tôi chọn hướng ở mỗi bước (tách dev/test, chọn reranker, cách tìm theo phiên bản, quy tắc chọn cấu hình) và duyệt kết quả trước khi commit. |
| Phản biện | AI chỉ ra các bẫy của starter với dữ liệu Day 6 (budget 800 ký tự, mất `alternative_gold`, quy tắc trùng trang) và các điểm yếu trong kết quả, như lựa chọn trên dev dựa vào chênh lệch rất nhỏ. |
| Tra cứu | AI đối chiếu điều khoản trong corpus khi viết câu hỏi và kiểm tra các câu thiếu bằng chứng bằng tìm kiếm trên toàn bộ chunk. |
| Kiểm tra | AI soạn nháp nhãn đánh giá bằng cách đọc từng câu trả lời với từng chunk, kèm lý do; tôi rà lại các nhãn, nhất là các nhãn quyết định kết quả, trước khi tổng hợp. |
