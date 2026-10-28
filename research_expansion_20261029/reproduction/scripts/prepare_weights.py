from common import ROOT,atomic_json,utc,sha
from prepare import download
def main():
    from torchvision.models import ResNet18_Weights
    url=ResNet18_Weights.IMAGENET1K_V1.url;p=ROOT/'cache/torch/hub/checkpoints'/url.split('/')[-1];p.parent.mkdir(parents=True,exist_ok=True)
    download(url,p,100<<20);h=sha(p);assert h.startswith('f37072fd')
    atomic_json(ROOT/'manifests/imagenet_weights.json',{'utc':utc(),'source':'torchvision.models.ResNet18_Weights.IMAGENET1K_V1','url':url,'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':h})
if __name__=='__main__':main()
