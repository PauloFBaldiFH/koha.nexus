# 9. Khắc phục sự cố và nhật ký

[Mục lục](README.md)

## Thu thập thông tin

Ghi hành động, giờ, toàn bộ lỗi và phần còn hoạt động. Trang mở, dịch vụ chạy và tìm kiếm được là các kiểm tra khác nhau. Không bắt đầu mọi sự cố bằng cài lại hoặc restore.

Làm mới **Control Dashboard**, đọc **Detailed server & Koha status**, **Full system health check** và **View latest validation report** trong **Diagnostics & maintenance center**. Khi cần **Export diagnostics**, giữ đường dẫn. Dù đã che một phần thông tin bí mật, vẫn kiểm tra bạn đọc, tên tệp và địa chỉ hạ tầng trước khi chia sẻ. Đừng sao chép toàn bộ thư mục cài. Chuyển về giao diện cổ điển không hoàn tác việc trước.

## Tìm và đọc nhật ký

Trong `/var/log/koha-easy-install/` có `apt.log`, `validacao-*.log`, `new-panel.log`, `backup_sql.log`, `backup_marc.log`, `restore.log`, `restore-import.log`, `zebra-rebuild.log`, `search-engine.log`. Công cụ dùng `/var/log/koha-easy-install/tools/`. Windows thường có `C:\Koha\logs`, bản cũ `C:\KohaEasy\logs`.

Dấu `*` đại diện phần ngày thay đổi, không phải tên cần tạo. Có thể chưa có log trước lần chạy đầu. Ưu tiên đường dẫn cụ thể trong lỗi. **View tool logs** chọn theo ngày/tác vụ; nội dung có thể chứa dữ liệu cá nhân. Báo cáo cần đọc bối cảnh, phiên bản, OK, cảnh báo và lỗi, không chỉ số cuối. **No critical failures** vẫn có thể có cảnh báo. Sau sửa hãy kiểm tra lại.

**Real-time Apache log auditing** cho staff hoặc OPAC. Textual **Pause** hay p chỉ dừng cập nhật màn hình, không dừng Apache; **Continue** tiếp tục, **Back**/Esc thoát. Ở giao diện cổ điển, Ctrl+C dành cho thoát theo dõi này, không áp dụng mọi tác vụ. Từ error/fatal/denied/fail nổi bật cần thời gian và ngữ cảnh để kết luận.

## Theo triệu chứng

Không vào được thì kiểm tra Apache, MariaDB, Plack, cache và địa chỉ local/LAN/VPN/tunnel. localhost thuộc máy trình duyệt. **Restart / repair Koha services (Memcached, Plack)** có thể ngắt truy cập ngắn; đọc kết quả và xác minh lại.

Biểu ghi không tìm được thì kiểm tra engine, hàng đợi và chỉ mục, dùng **Search engine & indexing > Repair / rebuild indexing** sau đọc câu hỏi và chờ xong. Không bắt buộc chuyển Elasticsearch trước tiên.

Backup thiếu: kiểm tra giờ, dung lượng, cron, máy/Linux có chạy. `.part` chưa hoàn chỉnh; tránh trùng việc và không xóa bản hợp lệ cuối khi chưa có bản an toàn khác. Nhập lỗi: so nguồn, chuẩn bị và số ghi thực, chế độ, mã, barcode, từ chối và trùng. Xem trước ít dòng không bảo đảm toàn tệp; xem phần đã ghi trước khi thử lại.

restore lỗi có thể sau khi cơ sở đã thay, rollback cũng có thể thất bại; kiểm tra cơ sở, tìm kiếm và báo cáo. AI chậm kiểm RAM/lựa chọn, bổ sung chậm kiểm tác vụ và máy chủ ngoài; không lặp việc lớn chỉ vì chưa có kết quả.

## Windows và hỗ trợ

Trong PowerShell của người đang đăng nhập, không chạy với quyền quản trị:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Công cụ không chỉ đọc; có thể tạo lại lối tắt và khởi động lại tray. Kết quả là `diagnose-<date>.txt` trong `logs` của bản cài được nhận diện. Giữ đường dẫn và lỗi.

**Deep database optimization & log cleanup** có thể xóa lịch sử hữu ích; giữ chẩn đoán trước và đặt giờ bảo trì, không dọn chỉ để che lỗi. Khi nhờ giúp, gửi phiên bản, OS/WSL, việc, giờ, toàn bộ thông báo, tình trạng OPAC/staff/tìm kiếm và thao tác nhập/restore/cập nhật trước đó sau kiểm tra riêng tư. Nguyên nhân cụ thể thiếu log đầy đủ vẫn cần xác nhận.

## Nguồn đã kiểm tra

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
