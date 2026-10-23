# 2. Bắt đầu và sử dụng bảng điều khiển

[Mục lục](README.md)

## Mở và điều hướng

Trên Debian hoặc Ubuntu đã được chuẩn bị:

```bash
sudo config.sh
```

Trên Windows dùng biểu tượng **Koha** hoặc ứng dụng MSIX. Lần đầu có thể hỏi ngôn ngữ. Nếu Textual không chuẩn bị được, trình khởi chạy có thể đưa ra giao diện cổ điển; số mục menu cũ không đại diện cho thẻ hiện tại.

Dùng phím mũi tên chọn mục ở thanh bên, Enter hoặc nhấp để mở. Di chuyển vùng chọn chưa chạy tác vụ. Mở thẻ phù hợp trong vùng nội dung và đọc câu hỏi trước khi xác nhận. Tab chuyển tiêu điểm giữa các điều khiển. Rời ô nhập trước khi dùng phím chữ của màn hình chính.

| Phím | Tác dụng trên màn hình chính |
| --- | --- |
| d | Mở Control Dashboard |
| b | Mở Backup center |
| c | Mở terminal Debian |
| Ctrl+B | Ẩn hoặc hiện thanh bên |
| q | Thoát bảng điều khiển |

Thoát khi không có tác vụ không phải tắt máy chủ. Khi đang làm việc, làm theo khả năng hủy của từng màn hình. Cài đặt và restore có giai đoạn không thể hủy; đóng cửa sổ cưỡng bức không phải cách dừng an toàn.

## Đọc trạng thái

**Control Dashboard** hiển thị Koha, RAM khả dụng, đĩa trống, tệp backup mới nhất và địa chỉ truy cập. Kiểm tra MariaDB, Apache, RabbitMQ, Memcached, Koha và HTTP có ích cho chẩn đoán, nhưng không xác nhận toàn bộ nghiệp vụ đã hoạt động.

Ngày và kích thước tệp mới nhất có thể khác lần chạy ban đêm được báo cáo. Có tệp mới vẫn có thể kèm lỗi tác vụ đêm. HTTP trả lời không chứng minh trình cài web Koha đã xong. **Refresh** đọc lại, **Restart Koha** yêu cầu sửa hoặc khởi động lại dịch vụ, **Export diagnostics** xuất thông tin. Nút có thể không khả dụng với trình cài cũ. Cân nhắc người đang dùng trước khi khởi động lại.

## Địa chỉ và bước đầu

Dùng thẻ địa chỉ để mở hoặc sao chép URL. Trên chính máy chủ, OPAC mặc định là `http://localhost/`, staff là `http://localhost:8080/`. localhost trên máy khác là máy đó, không phải máy chủ. Chọn địa chỉ mạng trong bảng điều khiển. Nếu WSL dùng NAT và báo mạng nội bộ không tới được, kiểm tra phần chuẩn bị mạng Windows trước.

Nếu staff còn hiển thị trình cài web, hoàn tất nó trước khi làm nghiệp vụ; các phiên bản Koha có thể khác bước. Sau đó **Koha settings & parameters > Create super librarian** mở luồng tạo tài khoản riêng. Chỉ nhập thông tin riêng tại hệ thống của mình và hạn chế quyền quản trị rộng.

Trước khi dùng thực tế, làm mới trạng thái, mở staff và OPAC, thử tìm kiếm, tạo và thử backup. Xác nhận bản ngoài máy chủ nằm ở đâu và ai phục hồi được. Đây là trách nhiệm vận hành; công cụ chuyển tệp chỉ hữu ích khi việc chuyển và kiểm tra thật sự hoàn tất.

## Nguồn đã kiểm tra

- [installer](../../../installer).
- [app.py](../../../panel/kei_panel/app.py).
- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [main.py](../../../panel/kei_panel/screens/main.py).
- [install.py](../../../panel/kei_panel/routines/install.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [dashboard.py](../../../panel/kei_panel/views/dashboard.py).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [menus.py](../../../panel/kei_panel/menus.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
