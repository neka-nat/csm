import torch
import torch.nn as nn
import torchvision


def upconv2d(in_planes, out_planes, mode='bilinear'):
    """
    Upsample + Convolution block

    :param in_planes: Number of input channels
    :param out_planes: Number of output channels
    :param mode: Upsample mode
    """
    
    upconv = nn.Sequential(
        nn.Upsample(scale_factor=2, mode=mode),
        nn.ReflectionPad2d(1),
        nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=1, padding=0),
        nn.LeakyReLU(0.2,inplace=True)
    )
    
    return upconv


def conv2d(batch_norm, in_planes, out_planes, kernel_size=3, stride=1):
    """
    Convolution + LeakyReLU block
    
    :param batch_norm: True or False. True if you want batchnormalizatoin layer
    :param in_planes: Number of input channels
    :param out_planes: Number of output channels
    :param kernel_size: Convolution kernel size
    :param stride: Convolution kernel stride
    """
    
    if batch_norm:
        return nn.Sequential(
            nn.Conv2d(in_planes, out_planes, kernel_size=kernel_size, stride=stride, padding=(kernel_size-1)//2, bias=True),
            nn.BatchNorm2d(out_planes),
            nn.LeakyReLU(0.2,inplace=True)
        )
    else:
        return nn.Sequential(
            nn.Conv2d(in_planes, out_planes, kernel_size=kernel_size, stride=stride, padding=(kernel_size-1)//2, bias=True),
            nn.LeakyReLU(0.2,inplace=True)
        )


def bilinear_init(kernel_size=4):
    # Following Caffe's BilinearUpsamplingFiller
    # https://github.com/BVLC/caffe/pull/2213/files
    import numpy as np
    width = kernel_size
    height = kernel_size
    f = int(np.ceil(width / 2.))
    cc = (2 * f - 1 - f % 2) / (2.*f)
    weights = torch.zeros((height, width))
    for y in range(height):
        for x in range(width):
            weights[y, x] = (1 - np.abs(x / f - cc)) * (1 - np.abs(y / f - cc))

    return weights


def net_init(net):
    """
    Initializes model model weights depending on the type of the layer

    :param net: Model for which the weights should be initialized 
    """
    
    for m in net.modules():
    
        if isinstance(m, nn.Linear):
    
            m.weight.data.normal_(0, 0.02)
            if m.bias is not None:
                m.bias.data.zero_()

        if isinstance(m, nn.Conv2d): #or isinstance(m, nn.ConvTranspose2d):
    
            m.weight.data.normal_(0, 0.02)
            if m.bias is not None:
                m.bias.data.zero_()

        if isinstance(m, nn.ConvTranspose2d):
    
            # Initialize Deconv with bilinear weights.
            base_weights = bilinear_init(m.weight.data.size(-1))
            base_weights = base_weights.unsqueeze(0).unsqueeze(0)
            m.weight.data = base_weights.repeat(m.weight.data.size(0), m.weight.data.size(1), 1, 1)
            if m.bias is not None:
                m.bias.data.zero_()

        if isinstance(m, nn.Conv3d) or isinstance(m, nn.ConvTranspose3d):
    
            m.weight.data.normal_(0, 0.02)
            if m.bias is not None:
                m.bias.data.zero_()

        elif isinstance(m, nn.BatchNorm2d) or isinstance(m, nn.BatchNorm3d):
            m.weight.data.fill_(1)
            m.bias.data.zero_()


def conv3x3(in_planes, out_planes, stride=1, groups=1, dilation=1):
    """3x3 convolution with padding"""
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride,
                     padding=dilation, groups=groups, bias=False, dilation=dilation)


def conv1x1(in_planes, out_planes, stride=1):
    """1x1 convolution"""
    return nn.Conv2d(in_planes, out_planes, kernel_size=1, stride=stride, bias=False)


def double_conv(in_planes, out_planes, mid_planes=None, batch_norm=False):
    """double convolution layers and keep dimensions"""
    if batch_norm is False:
        if mid_planes is None:
            return nn.Sequential(
                nn.Conv2d(in_planes, out_planes, 3, padding=1),
                nn.ReLU(inplace=True),
                nn.Conv2d(out_planes, out_planes, 3, padding=1),
                nn.ReLU(inplace=True)
            )
        else:
            return nn.Sequential(
                nn.Conv2d(in_planes, mid_planes, 3, padding=1),
                nn.ReLU(inplace=True),
                nn.Conv2d(mid_planes, out_planes, 3, padding=1),
                nn.ReLU(inplace=True)
            )
    else:
        if mid_planes is None:
            return nn.Sequential(
                nn.Conv2d(in_planes, out_planes, 3, padding=1),
                nn.BatchNorm2d(num_features=out_planes),
                nn.ReLU(inplace=True),
                nn.Conv2d(out_planes, out_planes, 3, padding=1),
                nn.BatchNorm2d(num_features=out_planes),
                nn.ReLU(inplace=True)
            )
        else:
            return nn.Sequential(
                nn.Conv2d(in_planes, mid_planes, 3, padding=1),
                nn.BatchNorm2d(num_features=mid_planes),
                nn.ReLU(inplace=True),
                nn.Conv2d(mid_planes, out_planes, 3, padding=1),
                nn.BatchNorm2d(num_features=out_planes),
                nn.ReLU(inplace=True)
            )


class ResNetConv(nn.Module):
    """resnet18 architecture with n blocks"""

    def __init__(self, n_blocks=4):
        super(ResNetConv, self).__init__()
        self.resnet = torchvision.models.resnet18(pretrained=True)
        self.n_blocks = n_blocks

    def forward(self, x):
        n_blocks = self.n_blocks
        x = self.resnet.conv1(x)
        x = self.resnet.bn1(x)
        x = self.resnet.relu(x)
        x = self.resnet.maxpool(x)

        if n_blocks >= 1:
            x = self.resnet.layer1(x)
        if n_blocks >= 2:
            x = self.resnet.layer2(x)
        if n_blocks >= 3:
            x = self.resnet.layer3(x)
        if n_blocks >= 4:
            x = self.resnet.layer4(x)

        return x


class Encoder(nn.Module):

    def __init__(self, trainable=True, num_in_chans: int = 3, num_feats: int = 100, input_shape=(256, 256)):
        """
        Loads resnet18 and extracts the pre-trained convolutional layers for feature extraction.
        Pre-trained layers are frozen.
        :param trainable: bool. whether to train the resnet layers.
        :param num_in_chans: Number of input channels. E.g. 3 for an RGB image, 4 for image + mask etc.
        :return: Feature extractor from resnet18 without classification head and one prepended 1x1 conv layer
        """

        super(Encoder, self).__init__()
        self.conv1 = torch.nn.Conv2d(in_channels=num_in_chans,
                                     out_channels=3, kernel_size=1)
        self.resnet = ResNetConv()
        if not trainable:
            # freeze pretrained resnet layers

            for param in resnet.parameters():
                param.requires_grad = False

        self.conv2 = nn.Sequential(
            nn.Conv2d(512, 256,  kernel_size=4, stride=2,
                      padding=(4-1)//2),
            nn.BatchNorm2d(256),
            nn.LeakyReLU(0.2, inplace=True))

        nc_input = 256 * (input_shape[0] // 64) * (input_shape[1] // 64)

        self.conv = nn.Sequential(self.conv1,
                                  self.resnet,
                                  self.conv2)

        self.fc = nn.Sequential(
            nn.Linear(nc_input, num_feats),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Linear(num_feats, num_feats),
            nn.LeakyReLU(0.2, inplace=True))

    def forward(self, img):
        # feats = self.conv(img)

        feats = self.conv1(img)
        feats = self.resnet(feats)
        feats = self.conv2(feats)

        feats = feats.view(img.size(0), -1)
        feats = self.fc(feats)
        return feats


def net_init(net):
    for m in net.modules():
        if isinstance(m, nn.Linear):
            #n = m.out_features
            # m.weight.data.normal_(0, 0.02 / n) #this modified initialization seems to work better, but it's very hacky
            #n = m.in_features
            # m.weight.data.normal_(0, math.sqrt(2. / n)) #xavier
            m.weight.data.normal_(0, 0.02)
            if m.bias is not None:
                m.bias.data.zero_()

        if isinstance(m, nn.Conv2d):  # or isinstance(m, nn.ConvTranspose2d):
            #n = m.kernel_size[0] * m.kernel_size[1] * m.in_channels
            # m.weight.data.normal_(0, math.sqrt(2. / n)) #this modified initialization seems to work better, but it's very hacky
            m.weight.data.normal_(0, 0.02)
            if m.bias is not None:
                m.bias.data.zero_()

        if isinstance(m, nn.BatchNorm2d) or isinstance(m, nn.BatchNorm3d):
            m.weight.data.fill_(1)
            m.bias.data.zero_()
