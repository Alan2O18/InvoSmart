import os
import time
import shutil
import logging
import cv2
from pathlib import Path
from typing import Optional
from backend.utils import utils

logger = logging.getLogger(__name__)

class FileOps:
    def __init__(self, project_repo, receipt_splitter, engine_ref):
        self.project_repo = project_repo
        self.receipt_splitter = receipt_splitter
        self.engine = engine_ref

    async def run_splitting(self, project_id: str, target_files: Optional[list[str]] = None):
        try:
            logger.info(f"[FileOps] run_splitting started for {project_id}, target_files={target_files}")
            root = self.project_repo._project_root(project_id)
            
            await self._prepare_tasks(root, project_id, target_files=target_files)
            
            await self.project_repo.update_project_status(project_id, "SPLIT")
            logger.info(f"[FileOps] run_splitting completed for {project_id}")
            return {"status": "split_completed"}
        except Exception as e:
            logger.error(f"[FileOps] Error splitting for {project_id}: {e}", exc_info=True)
            raise e

    async def _prepare_tasks(self, project_root: Path, project_id: str, target_files: Optional[list[str]] = None):
        raw_input_dir = project_root / "原始輸入"
        split_output_dir = project_root / "分割發票"
        
        if not raw_input_dir.exists():
            return

        files_to_process = []
        if target_files:
            files_to_process = target_files
        else:
            files_to_process = [f.name for f in raw_input_dir.iterdir() if f.is_file()]

        for image_name in files_to_process:
            try:
                image_path = raw_input_dir / image_name
                if not image_path.exists():
                    logger.warning(f"File not found: {image_path}")
                    continue

                if not image_name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    continue

                image = utils.cv_imread_chinese(str(image_path))
                if image is None:
                    logger.error(f"Failed to read image: {image_path}")
                    continue

                cropped_images = self.receipt_splitter.split(image, debug=False, headless=True)
                
                cropped_paths = []
                for i, img in enumerate(cropped_images):
                    ts = int(time.time())
                    save_path = split_output_dir / f"{image_path.stem}_split_{i}_{ts}.jpg"
                    utils.cv_imwrite_chinese(str(save_path), img)
                    cropped_paths.append(save_path)
                
                logger.info(f"[FileOps] Saved {len(cropped_paths)} split images for {image_name}")
                
                # Enqueue with ABSOLUTE paths
                for path in cropped_paths:
                    abs_path = str(path.resolve())
                    await self.engine.enqueue_job(project_id, abs_path)
                    logger.debug(f"[FileOps] Enqueued job with absolute path: {abs_path}")
                    
            except Exception as e:
                logger.error(f"Error preparing tasks for {image_name}: {e}")

    def get_raw_files(self, project_id: str):
        try:
            root = self.project_repo._project_root(project_id)
            raw_dir = root / "原始輸入"
            split_dir = root / "分割發票"
            
            if not raw_dir.exists():
                return []
                
            raw_files = []
            for f in os.listdir(raw_dir):
                if not f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    continue
                    
                base_name = os.path.splitext(f)[0]
                split_count = 0
                if split_dir.exists():
                    for sf in os.listdir(split_dir):
                        if sf.startswith(base_name + "_split_"):
                            split_count += 1
                            
                raw_files.append({
                    "filename": f,
                    "path": str(raw_dir / f),
                    "split_count": split_count
                })
            return raw_files
        except Exception as e:
            logger.error(f"Error getting raw files for {project_id}: {e}")
            return []

    async def add_project_files(self, project_id: str, files: list[str], type: str = "raw"):
        try:
            root = self.project_repo._project_root(project_id)
            if type == "raw":
                target_dir = root / "原始輸入"
            elif type == "split":
                target_dir = root / "分割發票"
            else:
                raise ValueError("Invalid type")
            
            target_dir.mkdir(parents=True, exist_ok=True)
            
            for file_path in files:
                filename = Path(file_path).name
                dest_path = target_dir / filename
                shutil.copy(file_path, dest_path)
                
                if type == "split":
                    # Enqueue with ABSOLUTE path
                    abs_path = str(dest_path.resolve())
                    await self.engine.enqueue_job(project_id, abs_path)
                    logger.debug(f"[FileOps] Enqueued split file with absolute path: {abs_path}")
            
            return {"status": "added"}
        except Exception as e:
            logger.error(f"Error adding files to {project_id}: {e}")
            raise e

    def rotate_image(self, project_id: str, filename: str, angle: int = 90):
        try:
            root = self.project_repo._project_root(project_id)
            image_path = root / "分割發票" / filename
            if not image_path.exists():
                raise FileNotFoundError(f"Image {filename} not found in splits")
            
            image = utils.cv_imread_chinese(str(image_path))
            if image is None:
                raise ValueError("Failed to read image")
            
            if angle == 90:
                image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
            elif angle == -90 or angle == 270:
                image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
            elif angle == 180:
                image = cv2.rotate(image, cv2.ROTATE_180)
            
            utils.cv_imwrite_chinese(str(image_path), image)
            return {"status": "rotated", "path": str(image_path)}
        except Exception as e:
            logger.error(f"Error rotating image {filename}: {e}")
            raise e
