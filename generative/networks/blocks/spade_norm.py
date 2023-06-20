from __future__ import annotations
import torch
import torch.nn as nn
from monai.networks.blocks import Convolution, ADN
import torch.nn.functional as F

class SPADE(nn.Module):
    """
    SPADE normalisation block based on the 2019 paper by Park et al. (doi: https://doi.org/10.48550/arXiv.1903.07291)
    Args:
        label_nc: number of semantic labels
        norm_nc: number of output channels
        kernel_size: kernel size
        spatial_dims: number of spatial dimensions
        hidden_channels: number of channels in the intermediate gamma and beta layers
        normalisation: type of base normalisation used before applying the SPADE normalisation
    """
    def __init__(self,
                 label_nc: int,
                 norm_nc: int,
                 kernel_size: int = 3,
                 spatial_dims: int = 2,
                 hidden_channels: int = 64,
                 norm: str | tuple= "INSTANCE",
                 norm_params: dict = {}
                 )-> None:

        super().__init__()

        if len(norm_params) != 0:
            norm = (norm, norm_params)
        self.param_free_norm = ADN(act=None, dropout=0.0, norm = norm,
                                   norm_dim=spatial_dims,
                                   ordering="N",
                                   in_channels=norm_nc)
        self.mlp_shared = Convolution(spatial_dims=spatial_dims,
                                      in_channels = label_nc,
                                      out_channels = hidden_channels,
                                      kernel_size= kernel_size,
                                      norm = None,
                                      padding=kernel_size//2,
                                      act="LEAKYRELU")
        self.mlp_gamma = Convolution(spatial_dims=spatial_dims,
                                     in_channels=hidden_channels,
                                     out_channels=norm_nc,
                                     kernel_size=kernel_size,
                                     padding = kernel_size//2,
                                     act = None
                                     )
        self.mlp_beta = Convolution(spatial_dims=spatial_dims,
                                     in_channels=hidden_channels,
                                     out_channels=norm_nc,
                                     kernel_size=kernel_size,
                                     padding = kernel_size//2,
                                     act = None
                                     )


    def forward(self,
                x: torch.Tensor,
                segmap: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: input tensor
            segmap: input segmentation map (bxcx[spatial-dimensions]) where c is the number of semantic channels.
            The map will be interpolated to the dimension of x internally.
        Returns:

        """

        # Part 1. generate parameter-free normalized activations
        normalized = self.param_free_norm(x)

        # Part 2. produce scaling and bias conditioned on semantic map
        segmap = F.interpolate(segmap, size=x.size()[2:], mode='nearest')
        actv = self.mlp_shared(segmap)
        gamma = self.mlp_gamma(actv)
        beta = self.mlp_beta(actv)
        out = normalized * (1 + gamma) + beta
        return out