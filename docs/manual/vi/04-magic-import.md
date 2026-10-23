# 4. Nhập dữ liệu thông minh

[Mục lục](README.md)

## Chuẩn bị nguồn

Mở **Magic Import Tool** bằng i hoặc thanh bên. Giữ tệp gốc và backup đã kiểm tra. Thử mẫu đại diện có nhiều bản tài liệu, dấu, ô rỗng và ngoại lệ, đối chiếu tổng với nguồn. Không công bố dữ liệu bạn đọc. Đường dẫn phải đọc được từ Linux đang chạy công cụ; tệp chỉ ở máy trình duyệt không tự có trên máy chủ.

Công cụ đọc MARC21 ISO 2709, MARCXML, MARC dạng văn bản `.mrk`, CSV/TSV, XLSX/XLS, ODS, DBF, JSON/XML dạng bảng và SQL nhận diện được. `.mrk` không mặc nhiên cần chuyển đổi. XML bất kỳ không chắc là MARCXML. SQL được trích dữ liệu, không chạy như chương trình chuyển cơ sở.

Bộ đọc ISIS riêng nhận xuất PostgreSQL có bảng `acervo`; với `.mst` CDS/ISIS, xuất ISO 2709 từ WinISIS. Biblioteca Fácil cần giữ các bảng liên quan và kiểm tra riêng thư mục, bạn đọc, mượn và đặt chỗ. Backup đầy đủ Koha chuyển sang restore có thay thế cơ sở. PostgreSQL của hệ khác, đặc biệt pg_dump nhị phân, không phải bản phục hồi MariaDB. Nếu không đọc được, xuất MARC hoặc bảng từ hệ nguồn. Với gói nén, đọc kết quả từng thành phần. PDF, ảnh, văn bản tài liệu và chương trình không phải dữ liệu thư mục dùng được.

## Ánh xạ thủ công

Kiểm tra **Bibliographic**, **Patrons**, **Authorities**, đổi chế độ nếu nhận sai. Trong bảng mẫu, chọn trường rồi xem giữ, chuyển đích, đặt văn bản cố định hoặc bỏ. Đừng bỏ mã liên kết trước khi hiểu quan hệ. Dùng thanh chia hoặc Ctrl+Up/Ctrl+Down để đổi chiều cao bảng.

**Values of this Koha** cho mã hợp lệ và giá trị mặc định của thư viện, loại tài liệu, nhóm bạn đọc, cùng ánh xạ mã nguồn sang mã đích. **Record preview** xem mẫu, **Check the whole file** chuẩn bị và kiểm tra toàn tệp nhưng chưa nhập vào Koha. Đặt tên cấu hình rồi **Save**; chọn cấu hình và **Use** để nạp. Cấu trúc nguồn đổi thì phải xem lại.

**Apply** hoặc Ctrl+S nhận ánh xạ và tiếp tục chuẩn bị, chưa phải xác nhận ghi cuối. Esc hoặc **Skip: import as it is** bỏ qua ánh xạ, không hủy cả luồng. Xem trước gộp trùng và sửa chữ hàng loạt, tránh làm hỏng tên riêng, chữ viết tắt và mã.

## Bản tài liệu, bạn đọc, biểu ghi chuẩn

`952` gốc Koha được giữ, có thể đổi mã thư viện và loại khi được yêu cầu. Mã khác mặc định chưa chắc sai. `949`, `852`, `950`, `990` mang nghĩa khác nhau giữa hệ thống; soát barcode, thư viện sở hữu/giữ, ký hiệu xếp giá, loại, vị trí và ngày nhận. Ghi chú lưu chiểu có `DL` không tự chứng minh có bản vật lý tại thư viện.

Barcode thiếu mặc định cần xem lại. Tạo mã thay thế cần lựa chọn rõ và định danh ổn định của nguồn/đợt chuyển, không âm thầm đánh số lại mã xung đột. Kiểm tra thiếu, trùng và va chạm với đích. SQL cần liên kết biểu ghi và bản bằng quan hệ nhận diện được, không đoán từ vị trí cột hay thứ tự dòng.

Ở bạn đọc, kiểm tra tên, họ, số thẻ, liên hệ, địa chỉ, ngày sinh/ghi danh/hết hạn, thư viện và nhóm. CPF, email và dạng ngày là dấu hiệu, không chứng minh phân loại đúng. Cập nhật theo số thẻ khác chỉ thêm mới; đọc lựa chọn. Không đoán cột quyền quản trị hay xác thực.

Ở biểu ghi chuẩn, kiểm tra mã, tiêu đề chuẩn, biến thể, quan hệ và loại. Đổi chế độ không tạo dữ liệu nguồn còn thiếu.

## Xác nhận và đối soát

Đọc tệp chuẩn bị, số lượng, từ chối và câu hỏi mã còn lại trước khi ghi. Giữ biểu ghi cũ và chỉ thêm bản, thay biểu ghi, hoặc bỏ so sánh và luôn thêm mới có tác dụng khác nhau.

Lỗi muộn không bảo đảm các giai đoạn trước đã hoàn tác. Giữ log, so số đã ghi rồi mới cân nhắc chạy lại. Kiểm tra Koha, bản tài liệu, bạn đọc và liên kết chuẩn. **Undo a MARC import** không hoàn tác chung bạn đọc, mượn và đặt chỗ. Tương thích với từng phiên bản hay bố cục riêng cần mẫu và xem kết quả, không được hứa chỉ vì nhận ra định dạng.

## Nguồn đã kiểm tra

- [menus.py](../../../panel/kei_panel/menus.py).
- [fieldmap.py](../../../panel/kei_panel/screens/fieldmap.py).
- [installer](../../../installer).
