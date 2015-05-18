import os
import hashlib


from Crypto.PublicKey import RSA
from simplehash import SimpleHash
from simpleauth import SimpleAuth
from crypto import mk_privkey, privtopub, sha3

class KeysAuth:
    def __init__( self, uuid = None ):
        self._privateKey = self._loadPrivateKey(str(uuid))
        self.publicKey = self._loadPublicKey(str(uuid))
        self.keyId = self.cntKeyId( self.publicKey )

    def getPublicKey( self ):
        return self.publicKey

    def getKeyId( self ):
        return self.keyId

    def cntKeyId( self, publicKey ):
        return self.publicKey


class RSAKeysAuth( KeysAuth ):

    def cntKeyId(self, publicKey):
        return SimpleHash.hash_hex(publicKey.exportKey("OpenSSH")[8:])

    def _getPrivateKeyLoc(self, uuid):
        if uuid is None:
            return os.path.normpath( os.path.join( os.environ.get( 'GOLEM' ), 'examples/gnr/node_data/golem_private_key.pem' ) )
        else:
            return os.path.normpath( os.path.join( os.environ.get( 'GOLEM' ), 'examples/gnr/node_data/golem_private_key{}.pem'.format(uuid)))

    def _getPublicKeyLoc(self, uuid):
        if uuid is None:
            os.path.normpath( os.path.join( os.environ.get('GOLEM'), 'examples/gnr/node_data/golem_public_key.pubkey') )
        else:
            return os.path.normpath( os.path.join( os.environ.get( 'GOLEM' ), 'examples/gnr/node_data/golem_public_key{}.pubkey'.format(uuid)))

    def _loadPrivateKey(self, uuid = None):
        privateKey = self._getPrivateKeyLoc( uuid )
        publicKey = self._getPublicKeyLoc( uuid )
        if not os.path.isfile( privateKey ) or not os.path.isfile( publicKey ):
            self._generateKeys( uuid )
        with open(privateKey) as f:
            key = f.read()
        key = RSA.importKey(key)
        return key

    def _loadPublicKey(self, uuid = None):
        privateKey = self._getPrivateKeyLoc( uuid )
        publicKey = self._getPublicKeyLoc( uuid )
        if not os.path.isfile(privateKey) or not os.path.isfile(publicKey):
            self._generateKeys( uuid )
        with open(publicKey) as f:
            key = f.read()
        key = RSA.importKey(key)
        return key

    def _generateKeys(self, uuid):
        privateKey = self._getPrivateKeyLoc( uuid )
        publicKey = self._getPublicKeyLoc( uuid )
        key = RSA.generate(2048)
        pubKey = key.publickey()
        with open( privateKey, 'w' ) as f:
            f.write( key.exportKey('PEM') )
        with open( publicKey, 'w') as f:
            f.write( pubKey.exportKey() )

class EllipticalKeysAuth( KeysAuth ):

    def cntKeyId( self, publicKey ):
        return publicKey.encode('hex')

    def _getPrivateKeyLoc(self, uuid):
        if uuid is None:
            return os.path.normpath( os.path.join( os.environ.get( 'GOLEM' ), 'examples/gnr/node_data/golem_private_key' ) )
        else:
            return os.path.normpath( os.path.join( os.environ.get( 'GOLEM' ), 'examples/gnr/node_data/golem_private_key{}'.format(uuid)))

    def _getPublicKeyLoc(self, uuid):
        if uuid is None:
            os.path.normpath( os.path.join( os.environ.get('GOLEM'), 'examples/gnr/node_data/golem_public_key') )
        else:
            return os.path.normpath( os.path.join( os.environ.get( 'GOLEM' ), 'examples/gnr/node_data/golem_public_key{}'.format(uuid)))

    def _loadPrivateKey(self, uuid = None):
        privateKey = self._getPrivateKeyLoc( uuid )
        publicKey = self._getPublicKeyLoc( uuid )
        if not os.path.isfile( privateKey ) or not os.path.isfile( publicKey ):
            self._generateKeys( uuid )
        with open(privateKey) as f:
            key = f.read()
        return key

    def _loadPublicKey(self, uuid = None):
        privateKey = self._getPrivateKeyLoc( uuid )
        publicKey = self._getPublicKeyLoc( uuid )
        if not os.path.isfile( privateKey ) or not os.path.isfile( publicKey ):
            self._generateKeys( uuid )
        with open(publicKey) as f:
            key = f.read()
        return key


    def _generateKeys( self, uuid ):
        privateKey = self._getPrivateKeyLoc( uuid )
        publicKey = self._getPublicKeyLoc( uuid )
        key = mk_privkey( str( SimpleAuth.generateUUID() ) )
        pubKey = privtopub( key )
        with open( privateKey, 'wb' ) as f:
            f.write( key )
        with open( publicKey, 'wb' ) as f:
            f.write( pubKey )



if __name__ == "__main__":
  #  auth = RSAKeysAuth()
    auth = EllipticalKeysAuth()
 #   print auth.getPublicKey()
  #  print auth.getKeyId()
  #  print auth.cntKeyId(auth.getPublicKey())

