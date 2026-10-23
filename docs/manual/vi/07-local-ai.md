# 7. AI cục bộ

[Mục lục](README.md)

## Cấu hình dịch vụ và tài nguyên

Nhấn a mở **AI** với nhà cung cấp, Ollama, MARC Replace và trợ lý staff. Cấu hình nhà cung cấp không tự cài mọi công cụ. Đọc cảnh báo CPU/RAM vì xử lý cục bộ có thể làm Koha chậm.

Dùng **Check Ollama**, khi cần **Install Ollama**, chọn và **Download**. Tải cần mạng và đĩa trống. Chọn **Local Ollama**, kiểm tra `http://127.0.0.1:11434`, dùng **Use for chat** hoặc **Use for cataloguing**. Ảnh cần khả năng thị giác, lựa chọn chỉ đọc văn bản không đọc được ảnh. **Test connection** hoặc F5 thử; **Save** hoặc Ctrl+S lưu. Điền trường chưa phải lưu.

Ô trò chuyện để trống dùng lựa chọn thị giác theo cấu hình. **Load models** hỏi danh sách nhà cung cấp; danh sách dự phòng không chứng minh đã cài. Tải chiếm đĩa, nạp trả lời chiếm RAM. **Free memory** dỡ khỏi RAM, không xóa tệp và có thể nạp lại khi hỏi tiếp. Khung Ollama vẫn hiện khi chọn nhà cung cấp khác: kiểm tra nhà cung cấp và URL đã lưu, không suy luận yêu cầu chạy cục bộ chỉ vì đã cài Ollama.

## Thay MARC và đọc ảnh

Cài hoặc cập nhật công cụ, kiểm tra biên dịch và liên kết staff rồi mở **MARC Replace**. Xử lý từng biểu ghi: chọn `.mrc`, `.xml` hay dán nội dung; nhập đúng `biblionumber` cần thay. Để trống là đường thêm mới, có thể trùng. **Preview** so bản hiện tại và đề xuất rồi xác nhận danh tính tài liệu.

Bản tài liệu đang có được giữ; trường bản từ nguồn vào bị loại. Bản cũ có thể tải MARCXML và gửi lại với cùng `biblionumber` theo chỉ dẫn. Không thay backup đầy đủ.

Trong **AI cataloguing**, gửi ít nhất một ảnh JPEG, PNG hoặc WebP rõ, gồm bìa, trang tên và mặt sau khi có. Chọn khung mới hoặc biểu ghi thay, **Read the photos** rồi kiểm tra nhan đề, tác giả, xuất bản, ISBN, phân loại và phần thiếu. Sửa MARC trước khi ghi. Số kiểm tra ISBN đúng không chứng minh đúng ấn bản; phân loại cần đối chiếu bảng của thư viện. Bản nháp không ghi trường bản tài liệu.

## Trợ lý và riêng tư

**Install, update or remove the assistant** đặt trò chuyện ở vị trí khối tin trang chủ staff, không đổi tin OPAC. Nó dùng tìm kiếm Koha và truy vấn đọc định trước, không chạy SQL tùy ý do AI viết.

Đề xuất chưa phải thay đổi. Xem bản đích, trước/sau và ảnh hưởng trước **Approve & Execute**; có kiểm tra quyền, dữ liệu đã đổi có thể yêu cầu đề xuất mới. Có thể xem thay đổi đã xác nhận. Xóa trò chuyện hay gỡ trợ lý không hoàn tác hành động; gỡ xóa hội thoại lưu và giữ lịch sử thay đổi đã xác nhận.

Theo dõi CPU/RAM và độ phản hồi Koha; không lặp việc lớn khi chậm. RAM, đĩa và thời gian tùy phần cứng, cần xác nhận. Nhà cung cấp từ xa nhận nội dung gửi đi; xét chính sách riêng tư, không thử với dữ liệu thật của bạn đọc. Nhãn phí trên giao diện không bảo đảm miễn phí.

## Nguồn đã kiểm tra

- [ai.py](../../../panel/kei_panel/views/ai.py).
- [marcreplace.py](../../../panel/kei_panel/marcreplace.py).
- [installer](../../../installer).
