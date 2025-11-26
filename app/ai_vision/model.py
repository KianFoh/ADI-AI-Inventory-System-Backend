import torchvision
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor


def get_model():
    """
    Returns a Faster R-CNN model for detecting empty slots only.
    - num_classes = 2 (background + empty)
    """

    num_classes = 2  # background + empty

    # Load Faster R-CNN model pre-trained on COCO
    model = torchvision.models.detection.fasterrcnn_resnet50_fpn(
        weights="COCO_V1")

    # Get number of input features for the classifier
    in_features = model.roi_heads.box_predictor.cls_score.in_features

    # Replace the pre-trained head with a new one for our dataset
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)

    return model