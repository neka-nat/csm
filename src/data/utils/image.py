from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import cv2
import numpy as np
import torch
from PIL import Image
from pytorch3d.renderer.mesh import Textures

from src.nnutils.geometry import convert_3d_to_uv_coordinates


def resize_img(img, scale_factor):
    new_size = (np.round(np.array(img.shape[:2]) * scale_factor)).astype(int)
    new_img = cv2.resize(img, (new_size[1], new_size[0]))
    # This is scale factor of [height, width] i.e. [y, x]
    actual_factor = [new_size[0] / float(img.shape[0]),
                     new_size[1] / float(img.shape[1])]
    return new_img, actual_factor


def peturb_bbox(bbox, pf=0, jf=0):
    """
    Jitters and pads the input bbox.

    Args:
        bbox: Zero-indexed tight bbox.
        pf: padding fraction.
        jf: jittering fraction.
    Returns:
        pet_bbox: Jittered and padded box. Might have -ve or out-of-image coordinates
    """
    pet_bbox = [coord for coord in bbox]
    bwidth = bbox[2] - bbox[0] + 1
    bheight = bbox[3] - bbox[1] + 1

    pet_bbox[0] -= (pf * bwidth) + (1 - 2 * np.random.random()) * jf * bwidth
    pet_bbox[1] -= (pf * bheight) + (1 - 2 * np.random.random()) * jf * bheight
    pet_bbox[2] += (pf * bwidth) + (1 - 2 * np.random.random()) * jf * bwidth
    pet_bbox[3] += (pf * bheight) + (1 - 2 * np.random.random()) * jf * bheight

    return pet_bbox


def square_bbox(bbox):
    """
    Converts a bbox to have a square shape by increasing size along non-max dimension.
    """

    sq_bbox = [int(round(coord)) for coord in bbox]
    bwidth = sq_bbox[2] - sq_bbox[0] + 1
    bheight = sq_bbox[3] - sq_bbox[1] + 1
    maxdim = float(max(bwidth, bheight))

    dw_b_2 = int(round((maxdim - bwidth) / 2.0))
    dh_b_2 = int(round((maxdim - bheight) / 2.0))

    sq_bbox[0] -= dw_b_2
    sq_bbox[1] -= dh_b_2
    sq_bbox[2] = sq_bbox[0] + maxdim - 1
    sq_bbox[3] = sq_bbox[1] + maxdim - 1

    return sq_bbox


def pad_to(img, size):

    H, W = img.shape[0], img.shape[1]
    pad = np.repeat(np.zeros(size)[:, :, None], img.shape[2], axis=2)
    pad[0:H, 0:W] = img
    return pad


def crop(img, bbox, bgval=0):

    """
    Crops a region from the image corresponding to the bbox.
    If some regions specified go outside the image boundaries, the pixel values are set to bgval.

    Args:
        img: image to crop
        bbox: bounding box to crop
        bgval: default background for regions outside image
    """
    bbox = [int(round(c)) for c in bbox]
    bwidth = bbox[2] - bbox[0] + 1
    bheight = bbox[3] - bbox[1] + 1

    im_shape = np.shape(img)
    im_h, im_w = im_shape[0], im_shape[1]

    nc = 1 if len(im_shape) < 3 else im_shape[2]

    img_out = np.ones((bheight, bwidth, nc)) * bgval
    x_min_src = max(0, bbox[0])
    x_max_src = min(im_w, bbox[2] + 1)
    y_min_src = max(0, bbox[1])
    y_max_src = min(im_h, bbox[3] + 1)

    x_min_trg = x_min_src - bbox[0]
    x_max_trg = x_max_src - x_min_src + x_min_trg
    y_min_trg = y_min_src - bbox[1]
    y_max_trg = y_max_src - y_min_src + y_min_trg

    img_out[y_min_trg:y_max_trg, x_min_trg:x_max_trg, :] = img[y_min_src:y_max_src, x_min_src:x_max_src, :]
    return img_out


def compute_dt(mask):
    """
    Computes distance transform of mask.
    """
    from scipy.ndimage import distance_transform_edt
    dist = distance_transform_edt(1 - mask) / max(mask.shape)
    return dist


def compute_dt_barrier(mask, k=50):
    """
    Computes barrier distance transform of mask.
    """
    from scipy.ndimage import distance_transform_edt
    dist_out = distance_transform_edt(1 - mask)
    dist_in = distance_transform_edt(mask)

    dist_diff = (dist_out - dist_in) / max(mask.shape)

    dist = 1. / (1 + np.exp(k * -dist_diff))
    return dist


def get_texture_map(img_path):

    texture_map = Image.open(img_path).resize((256, 256), Image.ANTIALIAS)
    texture_map = torch.from_numpy(np.asarray(texture_map)).permute(2, 0, 1)

    return texture_map.to(dtype=torch.float) / 255


def get_template_texture(vertices: torch.tensor, faces: torch.tensor, texture_map: torch.tensor):

    device = vertices.device

    verts_uv = convert_3d_to_uv_coordinates(vertices)
    vertex_rgb = torch.nn.functional.grid_sample(texture_map.unsqueeze(0),
                                                 2 * verts_uv.unsqueeze(0).unsqueeze(0) - 1)
    vertex_rgb = vertex_rgb.squeeze(2).permute(0, 2, 1) * 255
    texture = Textures([texture_map.permute(1, 2, 0)],
                       faces_uvs=faces.unsqueeze(0),
                       verts_uvs=verts_uv.unsqueeze(0),
                       verts_rgb=vertex_rgb).to(device)

    return texture
