# فونت فارسی برای PDF

`pdf_generator.py` برای نمایش صحیح متن فارسی (اتصال حروف + راست‌به‌چپ) نیاز به یک فونت
فارسی/عربی دارد. من در محیط ساخت این پاسخ دسترسی شبکه نداشتم تا فایل باینری فونت را مستقیم
داخل پروژه بگذارم، پس لطفاً یک‌بار همین‌جا (کنار پروژه، قبل از دیپلوی روی Render) دستور زیر را
اجرا کنید:

```bash
mkdir -p fonts
wget https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Regular.ttf -O fonts/Vazirmatn-Regular.ttf
wget https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Bold.ttf -O fonts/Vazirmatn-Bold.ttf
```

سپس این پوشه `fonts/` (همراه با دو فایل ttf) را به ریشه ریپوی گیت‌هاب پروژه commit و push کنید
تا روی Render هم موجود باشد.

اگر این دو فایل نباشند، ربات کرش نمی‌کند و PDF همچنان ساخته می‌شود، ولی حروف فارسی به‌جای
شکل درست، به‌صورت جدا از هم و نادرست نمایش داده خواهند شد.
