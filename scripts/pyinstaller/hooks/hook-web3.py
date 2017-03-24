import pkg_resources
from PyInstaller.utils.hooks import copy_metadata


web3 = pkg_resources.require('web3')
eggs = [r._provider.egg_info for r in web3]

datas = []
for req in web3:
    datas += copy_metadata(req.project_name)
