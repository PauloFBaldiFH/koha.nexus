# 1. Cài đặt

[Mục lục](README.md)

## Chọn môi trường

Trên Windows, Koha chạy trong Debian thuộc WSL 2. Công cụ Windows chuẩn bị môi trường, mở bảng điều khiển và tích hợp với máy tính. Trên Debian hoặc Ubuntu, dịch vụ được cài trực tiếp. Muốn dùng một hệ thống đã có thì mở bảng điều khiển, không cài lại.

Windows cần bản 64 bit, Windows 10 phiên bản 2004 build 19041 trở lên hoặc Windows 11, và bật ảo hóa trong BIOS/UEFI. RAM tối thiểu 8 GB, khuyến nghị 12 GB; dung lượng trống tối thiểu 10 GB, khuyến nghị 20 GB. Kiểm tra dùng ngưỡng 7.5 và 11.5 GB để tính phần RAM phần cứng giữ lại. Cần thêm chỗ cho tài liệu, tệp đính kèm, chỉ mục và backup.

Trình cài nhận diện Debian 11, 12, 13 và Ubuntu 22.04, 24.04 trên amd64 hoặc arm64. Dưới 5 GB trống sẽ bị chặn, từ 5 đến dưới 10 GB có cảnh báo. Hướng dẫn hiện có nêu máy chủ chuyên dụng tối thiểu 4 GB RAM, khuyến nghị 8 GB; máy để bàn hoặc môi trường ảo là 8/12 GB. Tuy nhiên, kiểm tra Linux chưa ép buộc mức RAM này bằng điều kiện số: yêu cầu chính thức cần xác nhận. Qua kiểm tra không bảo đảm đủ sức cho mọi thư viện.

WSL phải là WSL 2 có systemd; luồng này từ chối WSL 1. Linux cần quyền quản trị, truy cập kho Koha và các cổng 80, 8080. Chỉ đồng ý dừng dịch vụ đang chiếm cổng khi biết chắc có thể ngắt dịch vụ đó.

## Windows bằng PowerShell

Đăng nhập tài khoản Windows có quyền quản trị sẽ dùng Koha. Mở PowerShell với quyền quản trị trong chính tài khoản đó. Nếu yêu cầu tài khoản của người khác để nâng quyền, hủy và đăng nhập bằng tài khoản phù hợp. Sau khi kiểm tra nguồn và tin cậy tập lệnh, chạy:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Đọc kiểm tra máy, xử lý lỗi rồi trả lời câu hỏi tạo tài khoản Debian trong cửa sổ cài đặt. Tài khoản này khác tài khoản thư viện Koha. Khi cần khởi động lại, trình cài đăng ký tiếp tục ở lần đăng nhập Windows kế tiếp. Đăng nhập lại cùng người dùng, chọn ngôn ngữ và **Install Koha server**.

Khi hoàn tất trong bảng điều khiển, thoát bình thường rồi chờ tích hợp Windows kết thúc. Thư mục mặc định là `C:\Koha`; bản cũ có thể ở `C:\KohaEasy`. Không tự chuyển thư mục để sửa cài đặt dở dang. Chạy lại có thể tiếp tục các bước đã lưu, nhưng không làm cho thao tác cài lại có xóa dữ liệu trở nên an toàn.

## Gói MSIX

Mở PowerShell thông thường, không nâng quyền, và chạy công cụ hiện có:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

Công cụ kiểm tra nguồn và yêu cầu quyền cần thiết. Không bỏ qua thông báo bị từ chối. Cài gói xong chưa có nghĩa máy chủ Koha đã được thiết lập. Hoàn tất bước đầu trong bảng điều khiển, thoát bình thường rồi đợi cấu hình lối tắt, tác vụ nền và mạng. Nếu đóng sớm, mở ứng dụng lại để tiếp tục.

Tình trạng công khai và URL Microsoft Store cần xác nhận. Manifest hiện là x64: không suy luận MSIX chạy trên ARM64 chỉ vì Linux hỗ trợ arm64. Phiên bản Windows thấp hơn ghi trong manifest không thay thế yêu cầu của toàn bộ WSL.

## Debian, Ubuntu và cài máy chủ

Trên máy chủ đích:

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Hoặc giữ bản sao kho cùng các bản dịch:

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Chọn ngôn ngữ và **Install Koha server**. Đọc báo cáo, giải quyết lỗi nghiêm trọng, kiểm tra máy đích và múi giờ. Nếu phát hiện phiên bản đã cài, cài lại sẽ xóa cơ sở dữ liệu và cấu hình, yêu cầu đúng chữ `REINSTALL`. Trước khi chấp nhận, giữ một backup có thể khôi phục ở ngoài máy chủ.

Ước lượng 10 đến 30 phút có thể kéo dài tùy phần cứng và mạng. Bước này không thể hủy trong bảng điều khiển; đừng đóng cưỡng bức. Đọc kết quả cuối, vì hoàn thành kèm vấn đề không chứng minh mọi dịch vụ khỏe. Không đưa thông tin riêng từ màn hình kết quả vào tài liệu công khai.

## Nguồn đã kiểm tra

- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [installer](../../../installer).
- [README.md](../../../README.md).
- [install.ps1](../../../windows/install.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [instalar_msix.ps1](../../../windows/msix/instalar_msix.ps1).
- [KohaMsixEntry.cs](../../../windows/msix/KohaMsixEntry.cs).
- [KohaMsixPanel.ps1](../../../windows/KohaMsixPanel.ps1).
- [compilar_msix.ps1](../../../windows/msix/compilar_msix.ps1).
- [install.py](../../../panel/kei_panel/routines/install.py).
