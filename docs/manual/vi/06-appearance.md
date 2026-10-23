# 6. Giao diện OPAC và staff

[Mục lục](README.md)

## Quy trình thay đổi giao diện

Mở **OPAC and Staff Appearance** bằng o. OPAC công cộng và staff có cấu hình riêng. **Sync current OPAC settings** đọc hiện trạng, không áp dụng chủ đề mới. Sửa từng nhóm nhỏ rồi xem màu, độ rõ và ảnh.

**Preview** hiển thị CSS, JavaScript và nội dung sẽ ghi, không phải mô phỏng toàn trang trong trình duyệt. **Apply** tạo backup rồi xác nhận áp dụng. Sau đó thử trang chủ, tìm kiếm, biểu ghi, đăng nhập và màn hình nhỏ trên cả hai giao diện.

Khối quản lý nằm trong `OpacUserCSS`/`OpacUserJS`, và `IntranetUserCSS`/`IntranetUserJS` khi cần cho staff. Khối riêng của thư viện được giữ nhưng vẫn có thể xung đột hình ảnh. Cân nhắc tương phản khi đổi nền, độ trong suốt, mờ, góc và màu nhấn.

staff có bảng màu, thanh trên, tìm nhanh, thẻ mô-đun, mật độ bảng và cỡ chữ riêng. **Apply color theme to Staff Client** bật lựa chọn đó; **Copy OPAC preset** chỉ điền trường, vẫn cần **Apply**.

## Ảnh, băng chuyền và nút

Chọn tệp đọc được từ máy chủ, dịch vụ lưu ảnh được liệt kê, hoặc URL HTTPS trực tiếp. PNG, JPEG, GIF, WebP, ICO được nhận; SVG bị từ chối. Tệp ở máy người dùng chưa chắc máy chủ thấy được. Chỉ dùng ảnh có quyền, điền mô tả cho trình đọc màn hình. Địa chỉ trang lưu ảnh không nhất thiết là liên kết tệp ảnh. Không đăng thông tin riêng ở trang đăng nhập hay OPAC.

Băng chuyền dùng sách mới hoặc danh sách Koha. Lấy số danh sách từ `shelfnumber=` trong URL. Chỉnh tiêu đề, số lượng, kiểu, tốc độ và tự chạy, rồi **Refresh carousel**. Thiếu bìa không có nghĩa biểu ghi mất; nguồn bìa ngoài cần mạng.

Nút OPAC và nút trang chủ staff độc lập. Kiểm tra chữ, URL, nơi mở và thứ tự, dùng **Add a button** và nút xóa dòng trước khi áp dụng.

## Nội dung và tháo chủ đề

Khung đăng nhập có ảnh, mô tả và HTML đã lọc phần nguy hiểm như script, style, trình xử lý sự kiện. Không đặt hướng dẫn nội bộ mà khách không nên thấy. Tin của OPAC và staff có tiêu đề, nội dung và nút riêng; các mục do công cụ quản lý không thay tin độc lập do thư viện tạo.

Chân trang dùng `Field: value`, liên kết thêm dùng `Text|URL`, tối đa sáu liên kết. Chỉ đưa thông tin công khai.

**Remove** xác nhận và backup trước khi bỏ khối chủ đề, giữ tùy biến riêng. Đây không phải restore toàn cơ sở hay hoàn tác việc quản trị khác. Nếu chỉ sai ảnh hoặc màu, sửa đúng nhóm rồi áp dụng lại. Giữ thông báo đầy đủ nếu thao tác lỗi để điều tra.

## Nguồn đã kiểm tra

- [opac.py](../../../panel/kei_panel/views/opac.py).
- [menus.py](../../../panel/kei_panel/menus.py).
