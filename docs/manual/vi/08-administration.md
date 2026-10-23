# 8. Quản trị, thông báo và VPN

[Mục lục](README.md)

## Lịch và cấu hình

Kiểm tra hiện trạng và backup mới trước khi quản trị. Nhấn s mở **Schedules & cron tasks**, dùng **Reload**, bật việc cần, chọn tần suất và `HH:MM`, ngày hoặc biểu thức phù hợp. **Preview**, **Save**, đọc xác nhận rồi tải lại kiểm tra. **Defaults** chỉ điền mặc định, vẫn cần lưu.

Tệp quản lý là `/etc/cron.d/koha_tasks`, bản trước là `koha_tasks.bak`. Việc tắt còn dạng chú thích với giờ cũ; dòng tự viết được giữ. Mặc định SQL hàng ngày 23:00, MARC Chủ nhật 03:00 theo giờ máy chủ. Linux phải chạy; lịch không bảo đảm tự bật Windows. Thông báo nội bộ Koha có cơ chế riêng.

**Koha settings & parameters** điều chỉnh RAM, worker, múi giờ và tài khoản quyền rộng. **Koha languages** phân biệt tải và kích hoạt. **Update center** phân biệt gói hệ thống/cấu trúc Koha với cập nhật bảng điều khiển qua GitHub. Chuẩn bị backup và lịch bảo trì. Phiên làm việc có thể kết thúc; lỗi nâng cấu trúc không mặc nhiên hết sau khởi động lại.

## VPN và bảo mật

Trong **Security & access hub > WireGuard VPN**, hoặc v, nhập địa chỉ công khai và cổng UDP. **Set up the VPN** cho xem thay đổi; bộ định tuyến phải chuyển UDP tới máy chủ. **Add device**, chọn **QR code & profile** cho từng thiết bị rồi thử kết nối, staff và lưu lượng.

Hồ sơ và QR là riêng tư. **Revoke** làm hồ sơ cũ vô hiệu; muốn trở lại cần hồ sơ mới. **Turn off** ngắt nhưng giữ hồ sơ. Đường hầm tách chỉ đưa `10.66.0.0/24` qua VPN, internet và DNS còn theo kết nối thiết bị. staff tại `http://10.66.0.1:8080`. WSL không có mirrored networking bị báo không tới trực tiếp được và VPN này bị tắt.

Cloudflare Tunnel, UFW, hạn chế 8080, HTTPS và Fail2ban có phạm vi khác nhau. Không đổi tường lửa từ xa khi chưa biết đường quản trị còn lại. Domain, router, nhà mạng và chính sách cơ quan cần xác nhận, không có công thức công khai phù hợp mọi mạng.

## Thông báo và liên thông

Nhấn m mở **Messaging & interoperability**: **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2**, **Z39.50**. Bật email chưa cấu hình hết SMTP, địa chỉ thư viện, mẫu, quy tắc quá hạn và tùy chọn bạn đọc.

**Set up WhatsApp and Telegram** gồm dịch vụ, mã nước/vùng, thử và kiểm tra điện thoại. WhatsApp cần gateway, Telegram cần bot/người nhận. Thử với người được phép trước khi gửi thật, xem trước khi sửa số hàng loạt. SMS cần driver/dịch vụ tương thích ngoài `SMSSendDriver`.

**Alerts** đặt ngày đến hạn/quá hạn, lặp, tổng hợp và kênh; **Dry run (sends nothing)** chỉ mô phỏng. Bật việc thì kiểm tra cron, tránh trùng thông báo Koha. SIP2 cần cổng, mạng, thư viện, quyền thiết bị và tài khoản Koha tương ứng; bỏ ví dụ, không mở mọi mạng để thử tại chỗ. Z39.50 tìm ra ngoài khác phục vụ người khác tìm vào.

## Dữ liệu thư viện

**Library tools** có đồng bộ chuẩn, tác giả trùng, báo cáo SQL, đổi nhóm, chất lượng và riêng tư. Chọn nhóm nguồn/đích khác nhau, thư viện và điều kiện, xem chạy thử rồi backup trước xác nhận. Kiểm tra chất lượng chỉ đọc, không tự sửa mọi lỗi. Ẩn danh lịch sử bỏ liên kết với bạn đọc theo Koha, không xóa toàn bộ thư mục. Xóa bạn đọc cũ cần lọc, mô phỏng, xác nhận số và chính sách lưu giữ, là thao tác phá hủy. Tên giống nhau chưa chứng minh cùng người. Không coi thẻ bị ẩn là công cụ đang có sẵn.

## Nguồn đã kiểm tra

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
