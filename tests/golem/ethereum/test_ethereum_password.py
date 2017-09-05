import os
import stat
from golem.testutils import TempDirFixture

from golem.ethereum.password import get_saved_password, PASSWORD_LENGTH


class EthereumPasswordTest(TempDirFixture):

    def test_write_and_read(self):
        password1 = get_saved_password(self.tempdir)
        assert type(password1) is bytes
        assert len(password1) == PASSWORD_LENGTH
        password2 = get_saved_password(self.tempdir)
        assert type(password2) is bytes
        assert password1 == password2
        os.chmod(os.path.join(self.tempdir, 'password'), stat.S_IWRITE)

    def test_passwords_are_different(self):
        dir1 = os.path.join(self.tempdir, '1')
        dir2 = os.path.join(self.tempdir, '2')
        os.mkdir(dir1)
        os.mkdir(dir2)
        pass1 = get_saved_password(dir1)
        pass2 = get_saved_password(dir2)
        assert len(pass1) == PASSWORD_LENGTH
        assert len(pass2) == PASSWORD_LENGTH
        assert pass1 != pass2
        os.chmod(os.path.join(dir1, 'password'), stat.S_IWRITE)
        os.chmod(os.path.join(dir2, 'password'), stat.S_IWRITE)

    def test_empty_password_file(self):
        password_file = os.path.join(self.tempdir, 'password')
        with open(password_file, 'w'):
            pass
        assert os.path.exists(password_file)

        with self.assertRaises(IOError):
            get_saved_password(self.tempdir)

        os.chmod(password_file, stat.S_IWRITE)  # Allow deleting the file.
