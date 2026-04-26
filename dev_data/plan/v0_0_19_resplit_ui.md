# v0.0.19 Plan: Resplit & Stamp UI/UX Refactoring

## Goal Description

在前端影像裁切與座標擷取的使用體驗上遇到嚴重的「漂移」與操作問題：
1. **裁切結果與前端畫面不符**：手動細切與印章框選的結果，與前台顯示的座標發生偏差（漂移）。
2. **框會跑到外面**：自動識別帶出的框超出了實際影像區域。
3. **無法放大對準**：發票原始影像往往很大，預設縮放尺寸小，使用者難以放大並進行針對邊角的精確微調（四點透視變換對準）。

以上問題的**根本原因 (Root Cause)**：
- **手動細切 (ResplitModal)**：使用了 `object-fit: contain`。這導致 `<img>` 元素的實際大小包含了上下或左右的「黑邊補白 (Letterboxing)」，而覆蓋層卻直接綁定在 `clientWidth` 上，導致座標映射產生嚴重錯位。
- **印章框選 (StampAssignDialog)**：雖然使用了等比例的 `max-width`，但外層容器 (`preview-stage`) 帶有 `border: 1px solid`。透過 `getBoundingClientRect` 獲取的 `rect.width/height` 會包含邊框與小數點誤差，但繪製 `box-layer` 與計算 `scaleX` 時卻未扣除這些微小偏差，在原始影像極大的情況下，放大後誤差就會被突顯出來而產生座標漂移。
- **缺乏 Pan & Zoom 層**：兩個畫面階缺乏獨立的視圖轉換（Pan & Zoom）層，無法放大操作。

本計畫面臨的修正目標是完全重寫此兩個元件的影像與座標綁定邏輯，導入真正的 Pan & Zoom 機制，並確保前後端採用 1:1 無誤差的座標對齊。

## Proposed Changes

### Frontend Components

#### [MODIFY] [ResplitModal.vue](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/frontend/src/components/ResplitModal.vue)
- **座標系統重構 (Fix Box & Cut Offset)**
  - 移除 `object-fit: contain` 的黑邊補填。改用包裹的 `.transform-layer` 設定寬高等於相片原始 `naturalWidth` / `naturalHeight`。
  - `<svg>` 的 `viewBox` 直接設為 `0 0 naturalWidth naturalHeight`，使裡面繪製的任何多邊形完全對齊原圖座標 (1:1 Mapping)！
  - 徹底解決座標偏差。
- **Pan & Zoom 放大鏡效果導入**
  - 使用狀態 `transform { scale, x, y }` 保存當前視圖大小與位移。
  - 新增「放大」、「縮小」、「還原視角(Fit)」等輔助按鈕。
  - 綁定 `.canvas-host` 的 `@wheel`，以滑鼠游標為中心進行計算縮放。
  - 按住 `空白鍵` + `滑鼠左鍵拖曳` 來平移畫面 (平移時暫停點擊/拖曳事件)。
- **錨點拖曳座標推算**
  - 在拖曳端點時，根據 transform 回推自然 X、Y 座標。

#### [MODIFY] [StampAssignDialog.vue](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/frontend/src/components/StampAssignDialog.vue)
- **座標映射精準化 (Fix Stamp Drift)**
  - 移除含有 border 的 stage container 做為計算基準的寫法。
  - 改為直接綁定在 `img` 實體上的相對座標，或同樣導入 `viewBox="0 0 W H"` 的 SVG Layer 取代目前的 div border 框選。
  - 若維持 div 取底，確保 `clientX - imgBoundingRect.left` 與 `scale = naturalWidth / imgBoundingRect.width` 計算時完全不被 border/padding 干擾。
- **Pan & Zoom (若需要)**
  - 為印章選擇介面也加入相同的滑鼠中鍵 / 空白鍵平移與滾輪縮放邏輯，以利印章邊界的精細調整。

### Backend Services
- **影像 EXIF 與旋轉**
  - 確認 `stamp_service.py` 中的 `cv2.imdecode(..., cv2.IMREAD_COLOR)` 處，影像解碼後的維度與方向確與前端 Web 元件看到的（會自動套用 EXIF）完全一致。如有必要，加入依據 EXIF Auto-transpose 的實作。

## Verification Plan

### Manual Verification
1. **ResplitModal (發票手動二切)**
   - 載入後，紫框綠框必然完美貼齊邊緣，不跑出界不跑進黑邊。
   - 使用滾輪放大，按住空白鍵拖曳視角。
   - 修改四點透視角，送出套用後，新分割出的發票完美符合拖拉的形狀。
2. **StampAssignDialog (印章框選)**
   - 上傳印章影像圖紙。
   - 放大並詳細框選一個印章。
   - 確認畫面上呈現的虛線邊界與送出後切割出來的印章圖片完美疊合，杜絕先前的飄移狀況。
