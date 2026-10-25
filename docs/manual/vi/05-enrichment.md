# 5. Bổ sung dữ liệu và Z39.50/SRU

[Mục lục](README.md)

## Bổ sung biểu ghi đang có

Nhập đưa xuất liệu vào Koha; bổ sung tìm dữ liệu thêm cho biểu ghi hiện có hoặc tìm sách mới. Mở **Library tools > Enrich from world catalogues** hoặc n, không dùng màn hình lô cũ. Nhập `all` hoặc `biblionumbers` như `101, 102, 500-510`, rồi **Search**.

Theo dõi tác vụ và máy chủ. Tác vụ lớn chạy nền, có thể tiếp tục sau khởi động lại nếu máy còn khả dụng. **Pause**/**Resume** không hoàn tác thay đổi đã áp dụng. Mở báo cáo, so chủ đề, phân loại, ghi chú và mô tả vật lý. **Search more servers** hỏi nguồn chưa dùng; **Choose donor** chọn nguồn cho nhóm trường. Chỉ **Apply** sau xem xét và xác nhận; tìm và tạo báo cáo chưa ghi đề xuất vào mục lục.

Màn hình hiện dùng kết nối Z39.50 trực tiếp. Nguồn có giới hạn và lúc không truy cập được; chậm hay không có kết quả không chứng minh sách không tồn tại ở nơi khác. Không có giới hạn chung 50 biểu ghi. Khi áp dụng, lô nhỏ giữ bản biểu ghi, lô lớn dùng backup toàn bộ đã kiểm tra. Vẫn cần xem xét. **Revert** theo quy tắc bảo vệ, giữ biểu ghi bị sửa sau khi áp dụng; không tương đương restore toàn cơ sở.

## Sách mới và chuẩn hóa

Cùng màn hình, dùng ISBN hoặc nhan đề, tác giả, năm với **Find**. Kiểm tra nguồn rồi **Import as new record**. Nó thêm mới, không thay biểu ghi cùng ISBN. Các trường `9XX` cục bộ của nguồn bị loại và xuất xứ được lưu, tránh nhận bản của thư viện khác làm của mình. Tạo bản địa phương theo quy trình thư viện; đợt MARC tương ứng có thể dùng **Undo a MARC import**.

**Enrich & standardize authorities**, hoặc h, có khớp chính xác và dạng gần. Dạng gần có thể đề xuất sửa chính tả và tạo biểu ghi sơ bộ, cần kiểm tra. Luồng tìm trong Koha này trước, sau đó cơ sở bổ sung và máy chủ trực tiếp, ưu tiên nguồn Brazil và chỉ dùng nguồn Brazil cho chủ đề. Điều đó không bảo đảm phù hợp mọi chính sách biên mục.

Đọc báo cáo trước **Apply**; có backup an toàn, tạo chuẩn cần thiết và liên kết. Biểu ghi sửa sau khi lập báo cáo được giữ. Khi quay lại, chuẩn mới còn liên kết không bị xóa tùy tiện.

## Máy chủ và chiều kết nối

Mở **Z39.50 / SRU servers** hoặc z. Máy chủ của Koha này cho thư viện khác tìm; bật/tắt còn đổi cổng tường lửa. Mạng cộng đồng cấu hình nguồn dùng chung, khác máy chủ trực tiếp phục vụ bổ sung.

**Reset**/**Reset all** chỉ cho phép thử lại, không sửa dịch vụ từ xa. Chọn bằng Space, **Scan** thực hiện tìm thật rồi **Add to Koha** với nguồn hoạt động; không chỉ thử cổng. Hỗ trợ SRU trong cấu hình không có nghĩa mọi truy vấn bổ sung dùng SRU. Không cần mở dịch vụ nhận vào chỉ để tìm ở ngoài.

Khả dụng, phạm vi, điều kiện truy cập và kết nối từ mạng thư viện cần xác nhận tại thời điểm sử dụng.

## Nguồn đã kiểm tra

- [menus.py](../../../panel/kei_panel/menus.py).
- [ondemand.py](../../../panel/kei_panel/views/ondemand.py).
- [enrich.py](../../../panel/kei_panel/views/enrich.py).
- [z3950.py](../../../panel/kei_panel/views/z3950.py).
